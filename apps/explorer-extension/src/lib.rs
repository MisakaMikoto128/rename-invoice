//! invoice_shext.dll — rename-invoice 资源管理器扩展
//!
//! 通过稀疏 MSIX 包 (desktop4:FileExplorerContextMenus) 注册进 Windows 11
//! 顶层右键菜单。Explorer 对选中项集合调用 IExplorerCommand:
//!   - GetState 过滤: 选中项里没有 PDF/文件夹时隐藏本命令
//!   - Invoke 把选中路径转发给 invoice-cli (配置在注册表, 见 scripts/install.ps1)
//!
//! 多选时 Invoke 只触发一次, 天然规避注册表 verb 每文件一进程的 N 次弹窗问题。

use std::ffi::c_void;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;

use windows::core::{
    implement, w, BOOL, Error, IUnknown, Interface, Ref, Result, GUID, PCWSTR, PWSTR,
};
use windows::Win32::Foundation::{
    CLASS_E_CLASSNOTAVAILABLE, CLASS_E_NOAGGREGATION, E_FAIL, E_NOTIMPL, E_OUTOFMEMORY,
    E_POINTER, HMODULE, S_FALSE,
};
use windows::Win32::System::Com::{
    CoTaskMemAlloc, CoTaskMemFree, IBindCtx, IClassFactory, IClassFactory_Impl,
};
use windows::Win32::System::LibraryLoader::{
    GetModuleFileNameW, GetModuleHandleExW, GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,
    GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
};
use windows::Win32::System::Registry::{RegGetValueW, HKEY_CURRENT_USER, RRF_RT_REG_SZ};
use windows::Win32::UI::Shell::{
    IEnumExplorerCommand, IExplorerCommand, IExplorerCommand_Impl, IShellItem, IShellItemArray,
    ECF_DEFAULT, ECS_ENABLED, ECS_HIDDEN, SIGDN_FILESYSPATH,
};

/// COM 类标识。装完就永远固定, 换了等于逼所有用户重装。
const CLSID_INVOICE_EXT: GUID = GUID::from_u128(0x377B2F61_66A6_4688_A5BE_82AD42F3ADF6);

/// 命令的规范名 (canonical name), 与 CLSID 无关, 仅作标识。
const CMD_CANONICAL: GUID = GUID::from_u128(0x6966CFB4_0735_4F41_AB79_7565DE388EC9);

/// 注册表配置位置 (install.ps1 写入): ExePath + Args
const CONFIG_SUBKEY: PCWSTR = w!("Software\\rename-invoice\\ExplorerExt");

/// CREATE_NO_WINDOW — 给控制台子进程用; GUI 子进程 (pythonw) 本来就无窗口。
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

// ---------------------------------------------------------------- COM 入口

/// Explorer CoCreateInstance(CLSID) 的入口: 返回 IClassFactory。
#[no_mangle]
extern "system" fn DllGetClassObject(
    rclsid: *const GUID,
    riid: *const GUID,
    ppv: *mut *mut c_void,
) -> windows::core::HRESULT {
    unsafe {
        if rclsid.is_null() || riid.is_null() || ppv.is_null() {
            return E_POINTER;
        }
        if *rclsid != CLSID_INVOICE_EXT {
            return CLASS_E_CLASSNOTAVAILABLE;
        }
        let factory: IClassFactory = ClassFactory.into();
        factory.query(riid, ppv)
    }
}

/// 永远返回 S_FALSE: DLL 常驻 Explorer 进程, 不允许卸载。
/// (精确回收引用计数需要额外的对象计数器, 换来的只是省几 MB 内存)
#[no_mangle]
extern "system" fn DllCanUnloadNow() -> windows::core::HRESULT {
    S_FALSE
}

// ---------------------------------------------------------------- IClassFactory

#[implement(IClassFactory)]
struct ClassFactory;

impl IClassFactory_Impl for ClassFactory_Impl {
    fn CreateInstance(
        &self,
        punkouter: Ref<'_, IUnknown>,
        riid: *const GUID,
        ppvobject: *mut *mut c_void,
    ) -> Result<()> {
        if punkouter.is_some() {
            return Err(Error::from(CLASS_E_NOAGGREGATION));
        }
        unsafe {
            if riid.is_null() || ppvobject.is_null() {
                return Err(Error::from(E_POINTER));
            }
            let command: IExplorerCommand = InvoiceCommand.into();
            command.query(riid, ppvobject).ok()
        }
    }

    fn LockServer(&self, _flock: BOOL) -> Result<()> {
        Ok(())
    }
}

// ---------------------------------------------------------------- IExplorerCommand

#[implement(IExplorerCommand)]
struct InvoiceCommand;

impl IExplorerCommand_Impl for InvoiceCommand_Impl {
    fn GetTitle(&self, _itemarray: Ref<'_, IShellItemArray>) -> Result<PWSTR> {
        co_task_str("添加发票价格前缀")
    }

    fn GetIcon(&self, _itemarray: Ref<'_, IShellItemArray>) -> Result<PWSTR> {
        let Some(dir) = dll_dir() else {
            return Err(Error::from(E_FAIL));
        };
        let icon = dir.join("assets").join("icon.ico");
        if !icon.is_file() {
            return Err(Error::from(E_FAIL));
        }
        co_task_str(&format!("{},0", icon.display()))
    }

    fn GetToolTip(&self, _itemarray: Ref<'_, IShellItemArray>) -> Result<PWSTR> {
        co_task_str("对选中的发票 PDF / 文件夹执行三层金额校验并重命名 (静默)")
    }

    fn GetCanonicalName(&self) -> Result<GUID> {
        Ok(CMD_CANONICAL)
    }

    fn GetState(&self, itemarray: Ref<'_, IShellItemArray>, _foktobeslow: BOOL) -> Result<u32> {
        let Ok(array) = itemarray.ok() else {
            return Ok(ECS_ENABLED.0 as u32);
        };
        if selection_has_target(array) {
            Ok(ECS_ENABLED.0 as u32)
        } else {
            Ok(ECS_HIDDEN.0 as u32)
        }
    }

    fn Invoke(&self, itemarray: Ref<'_, IShellItemArray>, _pbc: Ref<'_, IBindCtx>) -> Result<()> {
        let Ok(array) = itemarray.ok() else {
            return Err(Error::from(E_FAIL));
        };
        invoke_cli(array)
    }

    fn GetFlags(&self) -> Result<u32> {
        Ok(ECF_DEFAULT.0 as u32)
    }

    fn EnumSubCommands(&self) -> Result<IEnumExplorerCommand> {
        Err(Error::from(E_NOTIMPL))
    }
}

// ---------------------------------------------------------------- 实现

/// 选中项里是否有本工具的目标 (.pdf 文件或任意文件夹)。
/// 没有就返回 false, GetState 用它把命令从菜单里隐藏。
fn selection_has_target(array: &IShellItemArray) -> bool {
    let mut found = false;
    for_each_path(array, |_path| {
        found = true;
    });
    found
}

/// 枚举选中项的文件系统路径; 虚拟位置 (回收站等) 拿不到路径, 静默跳过。
fn for_each_path<F: FnMut(String)>(array: &IShellItemArray, mut f: F) {
    let count = unsafe { array.GetCount().unwrap_or(0) };
    for i in 0..count {
        let item: IShellItem = match unsafe { array.GetItemAt(i) } {
            Ok(v) => v,
            Err(_) => continue,
        };
        if let Ok(name) = unsafe { item.GetDisplayName(SIGDN_FILESYSPATH) } {
            f(unsafe { name.to_string() }.unwrap_or_default());
            unsafe { CoTaskMemFree(Some(name.0.cast())) };
        }
    }
}

/// 读注册表里的 CLI 配置, 返回 (ExePath, Args)。
fn read_cli_config() -> Option<(String, String)> {
    let exe = reg_read_string(CONFIG_SUBKEY, w!("ExePath"))?;
    let args = reg_read_string(CONFIG_SUBKEY, w!("Args")).unwrap_or_default();
    Some((exe, args))
}

fn reg_read_string(subkey: PCWSTR, value: PCWSTR) -> Option<String> {
    let mut buf = [0u8; 2048];
    let mut cb: u32 = buf.len() as u32;
    let err = unsafe {
        RegGetValueW(
            HKEY_CURRENT_USER,
            subkey,
            value,
            RRF_RT_REG_SZ,
            None,
            Some(buf.as_mut_ptr().cast()),
            Some(&mut cb),
        )
    };
    if err.0 != 0 || cb < 2 {
        return None;
    }
    // cb 按字节计, 含结尾 NUL — 重建 UTF-16 切片
    let chars: &[u16] =
        unsafe { std::slice::from_raw_parts(buf.as_ptr().cast(), (cb as usize) / 2 - 1) };
    Some(String::from_utf16_lossy(chars))
}

/// 把选中路径作为参数追加到 CLI 命令行并启动。
/// CLI 自身有文件锁队列: 多次 Invoke 并发时会在 CLI 侧合并成一次处理。
fn invoke_cli(array: &IShellItemArray) -> Result<()> {
    let (exe, args) = read_cli_config().ok_or_else(|| {
        Error::new(
            E_FAIL,
            "未找到注册表配置 Software\\rename-invoice\\ExplorerExt (先运行 scripts/install.ps1)",
        )
    })?;

    let mut paths = Vec::new();
    for_each_path(array, |p| paths.push(p));
    if paths.is_empty() {
        return Ok(());
    }

    let mut cmd = Command::new(&exe);
    if !args.is_empty() {
        cmd.raw_arg(&args);
    }
    for p in &paths {
        cmd.raw_arg(quote_arg(p));
    }
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd.spawn()
        .map_err(|e| Error::new(E_FAIL, format!("启动 CLI 失败 ({}): {}", exe, e)))?;
    Ok(())
}

/// IExplorerCommand 的字符串出参由调用方 CoTaskMemFree, 必须用 CoTaskMemAlloc 分配。
fn co_task_str(s: &str) -> Result<PWSTR> {
    let mut wide: Vec<u16> = s.encode_utf16().collect();
    wide.push(0);
    let byte_len = wide.len() * std::mem::size_of::<u16>();
    let ptr = unsafe { CoTaskMemAlloc(byte_len) };
    if ptr.is_null() {
        return Err(Error::from(E_OUTOFMEMORY));
    }
    unsafe { std::ptr::copy_nonoverlapping(wide.as_ptr(), ptr.cast::<u16>(), wide.len()) };
    Ok(PWSTR(ptr.cast::<u16>()))
}

/// Windows 命令行引号规则: 含空格/制表/引号时加双引号并转义内部引号与反斜杠。
fn quote_arg(arg: &str) -> String {
    if !arg.is_empty()
        && !arg.bytes().any(|b| b == b' ' || b == b'\t' || b == b'"')
        && !arg.ends_with('\\')
    {
        return arg.to_string();
    }
    let mut out = String::with_capacity(arg.len() + 2);
    out.push('"');
    let mut backslashes = 0usize;
    for ch in arg.chars() {
        match ch {
            '\\' => {
                backslashes += 1;
                out.push('\\');
            }
            '"' => {
                out.push_str(&"\\".repeat(backslashes * 2 + 1));
                out.push('"');
                backslashes = 0;
            }
            _ => {
                backslashes = 0;
                out.push(ch);
            }
        }
    }
    if backslashes > 0 {
        out.push_str(&"\\".repeat(backslashes));
    }
    out.push('"');
    out
}

/// 本 DLL 所在目录 (图标等资源相对于它)。
fn dll_dir() -> Option<PathBuf> {
    // 用一个 static 的地址定位宿主模块: 它一定落在本 DLL 的映像里
    static ANCHOR: u8 = 0;

    let mut module = HMODULE::default();
    let ok = unsafe {
        GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            PCWSTR((&ANCHOR as *const u8).cast()),
            &mut module,
        )
    };
    if ok.is_err() {
        return None;
    }
    let mut buf = [0u16; 1024];
    let len = unsafe { GetModuleFileNameW(Some(module), &mut buf) } as usize;
    if len == 0 {
        return None;
    }
    PathBuf::from(String::from_utf16_lossy(&buf[..len]))
        .parent()
        .map(|p| p.to_path_buf())
}
