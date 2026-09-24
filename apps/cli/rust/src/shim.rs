//! rename-invoice-w.exe — 右键菜单前置 shim (windows 子系统, 0 cmd 闪窗)
//!
//! # 为什么需要它
//!
//! Windows 的 legacy verb (`shell\<Verb>\command` + `%1`) 是 "Document/Player" 模型:
//! **选中 N 个文件, Explorer 就 CreateProcess N 次**, 每次只塞一个文件路径进去.
//! 这个行为我们改不了 (除非做 COM DropTarget), 能改的只有"每个进程有多重".
//!
//! 之前注册表直接指向完整的 10 MB 主程序, 于是全选 23 个 PDF = 启动 23 个
//! 10 MB 进程 (还各自要 load pdfium.dll / slint). 现在拆成:
//!
//!   Explorer ──N 次──> rename-invoice-w.exe (本文件, ~几百 KB)
//!                        1. 过闸门 (同时最多 MAX_PROCS 个, 默认 12)
//!                        2. 把自己那条路径追加进 .queue.txt
//!                        3. 没有 worker 就拉起 1 个 rename-invoice.exe
//!                        4. 立刻退出
//!                                    │ 只拉 1 个
//!                                    ▼
//!                      rename-invoice.exe --silent --from-queue  (重进程, 全程只有 1 个)
//!                        排空队列, 处理全部 PDF, 出 xlsx / 汇总窗口
//!
//! 结果: 重进程恒为 1 个; N 个轻进程各自活几毫秒就退.
//!
//! # 闸门 (MAX_PROCS)
//!
//! 用一个 Windows 命名信号量把**同时在跑的 shim** 限制在 12 个 (可用环境变量
//! RENAME_INVOICE_MAX_PROCS 调整). 超出的那些不是被丢弃, 而是在信号量上短暂排队,
//! 所以一个文件都不会丢. 12 是按普通办公机 (4~8 核 / 机械盘或 SATA SSD) 取的:
//! 再多就只是让 .queue.lock 上的争抢和杀软扫描互相拖慢, 不会更快.
//!
//! 注意入队在闸门**之后**、判断在入队**之后** —— 顺序不能换, 见 queue.rs 注释.

#[path = "log_audit.rs"]
mod log_audit;
#[path = "queue.rs"]
mod queue;

use std::path::PathBuf;

const DEFAULT_MAX_PROCS: u32 = 12;
/// 闸门等不到就直接放行. 宁可多几个进程, 也不能让用户的文件卡住不处理.
const GATE_TIMEOUT_MS: u32 = 5_000;

struct Flags {
    summary: bool,
    xlsx: bool,
}

fn parse() -> (Flags, Vec<PathBuf>) {
    let mut flags = Flags {
        summary: false,
        xlsx: false,
    };
    let mut paths = Vec::new();
    for arg in std::env::args().skip(1) {
        match arg.as_str() {
            // --silent 是注册表命令里固定带的, shim 本来就只有静默这一种行为
            "--silent" | "--from-queue" => {}
            "--summary" => flags.summary = true,
            "--xlsx" => flags.xlsx = true,
            _ => paths.push(PathBuf::from(arg)),
        }
    }
    (flags, paths)
}

fn max_procs() -> u32 {
    std::env::var("RENAME_INVOICE_MAX_PROCS")
        .ok()
        .and_then(|s| s.trim().parse::<u32>().ok())
        .filter(|n| *n >= 1)
        .unwrap_or(DEFAULT_MAX_PROCS)
}

fn worker_exe() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let worker = dir.join("rename-invoice.exe");
    if worker.exists() {
        Some(worker)
    } else {
        None
    }
}

#[cfg(windows)]
fn spawn_worker(flags: &Flags) -> std::io::Result<()> {
    use std::os::windows::process::CommandExt;
    use std::process::{Command, Stdio};

    // rename-invoice.exe 是 console 子系统, 不给 CREATE_NO_WINDOW 会闪一下黑框.
    // DETACHED_PROCESS 不能用: 那样 worker 弹 Slint 汇总窗口时拿不到正常的窗口站.
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;

    let worker = worker_exe().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "找不到 rename-invoice.exe (应与 rename-invoice-w.exe 同目录)",
        )
    })?;

    let mut cmd = Command::new(worker);
    // --from-queue: 不要再把命令行路径入队 (shim 已经入过了), 也不要默认拿 cwd 兜底
    cmd.arg("--silent").arg("--from-queue");
    if flags.summary {
        cmd.arg("--summary");
    }
    if flags.xlsx {
        cmd.arg("--xlsx");
    }
    cmd.creation_flags(CREATE_NO_WINDOW)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;
    Ok(())
}

#[cfg(not(windows))]
fn spawn_worker(_flags: &Flags) -> std::io::Result<()> {
    Ok(())
}

// ---------------------------------------------------------------------------
// 闸门: 命名信号量, 限制同时在跑的 shim 数量
// ---------------------------------------------------------------------------

#[cfg(windows)]
mod gate {
    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE, WAIT_OBJECT_0};
    use windows_sys::Win32::System::Threading::{
        CreateSemaphoreW, ReleaseSemaphore, WaitForSingleObject,
    };

    /// Local\ 前缀 = 每个登录会话一份, 不需要任何特权, 多用户互不干扰.
    const GATE_NAME: &str = "Local\\rename-invoice-shim-gate";

    pub struct Gate {
        handle: HANDLE,
        held: bool,
    }

    impl Gate {
        /// 拿到名额返回 Gate; 超时也返回 Gate (held=false) 直接放行.
        ///
        /// 信号量在最后一个句柄关闭时被内核销毁, 所以即使某个 shim 崩溃导致
        /// 计数泄漏, 也只影响这一波右键, 下一波会重新从满额开始.
        pub fn acquire(max: u32, timeout_ms: u32) -> Gate {
            let name: Vec<u16> = GATE_NAME.encode_utf16().chain(std::iter::once(0)).collect();
            let handle = unsafe {
                CreateSemaphoreW(
                    std::ptr::null(),
                    max as i32,
                    max as i32,
                    name.as_ptr(),
                )
            };
            if handle.is_null() {
                return Gate {
                    handle: std::ptr::null_mut(),
                    held: false,
                };
            }
            let held = unsafe { WaitForSingleObject(handle, timeout_ms) } == WAIT_OBJECT_0;
            Gate { handle, held }
        }
    }

    impl Drop for Gate {
        fn drop(&mut self) {
            if self.handle.is_null() {
                return;
            }
            if self.held {
                unsafe { ReleaseSemaphore(self.handle, 1, std::ptr::null_mut()) };
            }
            unsafe { CloseHandle(self.handle) };
        }
    }
}

#[cfg(not(windows))]
mod gate {
    pub struct Gate;
    impl Gate {
        pub fn acquire(_max: u32, _timeout_ms: u32) -> Gate {
            Gate
        }
    }
}

fn main() {
    // shim 是 windows 子系统, 没有 stdout/stdin, 装不了也卸不了 (install 要交互两问).
    // 用户手滑跑 `rename-invoice-w.exe install` 的话, 不要把 "install" 当成路径入队.
    if let Some(sub) = std::env::args().nth(1) {
        if sub == "install" || sub == "uninstall" {
            log_audit::log_line(&format!(
                "FAIL  (shim) `{}` 请用 rename-invoice.exe 执行, rename-invoice-w.exe 没有控制台",
                sub
            ));
            return;
        }
    }

    let (flags, paths) = parse();

    // 闸门先于一切: 限制同时在跑的 shim 数量
    let _gate = gate::Gate::acquire(max_procs(), GATE_TIMEOUT_MS);

    let paths: Vec<PathBuf> = if paths.is_empty() {
        // 无参数 = 从文件夹空白处右键但 %V 没展开, 兜底用 cwd
        std::env::current_dir().into_iter().collect()
    } else {
        paths
    };
    if paths.is_empty() {
        return;
    }

    // 顺序关键: 先入队, 再判断要不要拉 worker.
    // 反过来的话, worker 刚好在这两步之间退出, 我们这条路径就没人处理了.
    if let Err(e) = queue::append_to_queue(&paths) {
        log_audit::log_line(&format!("FAIL  (shim) 写入队列失败: {}", e));
        return;
    }

    match queue::spawn_worker_if_needed(|| spawn_worker(&flags)) {
        Ok(_) => {}
        Err(e) => log_audit::log_line(&format!("FAIL  (shim) 拉起 rename-invoice.exe 失败: {}", e)),
    }
}
