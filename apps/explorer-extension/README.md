# invoice-explorer-extension — 资源管理器插件 (程序 3)

把 **"添加发票价格前缀"** 直接放进 **Windows 11 顶层右键菜单**（带图标、悬停提示、
单选/多选/文件夹全支持），不再需要钻进"显示更多选项"。

```text
选中发票.pdf → 右键 → 📄 添加发票价格前缀   ← 顶层直达, 不用点"显示更多选项"
```

## 它是怎么工作的

| 组件 | 说明 |
|---|---|
| `invoice_shext.dll` | Rust 写的 COM DLL，实现 `IExplorerCommand`（Windows 11 现代菜单的官方扩展点） |
| 稀疏 MSIX 包 | `package/AppxManifest.xml` + `desktop4:FileExplorerContextMenus`，把命令注册进现代菜单；DLL 以"外部位置"形式留在源码树，不复制进系统 |
| invoice-cli | 真正干活的还是 [程序 1](../cli/)：DLL 只把选中的路径转发给 `pythonw.exe apps/cli/rename_invoice.py --silent`，三层金额校验逻辑完全复用 |

与经典注册表 verb（程序 1 自带的右键菜单）相比：

| | 经典 verb（程序 1） | 本插件（程序 3） |
|---|---|---|
| 菜单位置 | "显示更多选项"里 | **顶层**，带图标 |
| 多选 10 个 PDF | Windows 触发 10 次调用（靠 CLI 文件锁合并） | **Invoke 一次拿到全部选中项**，天然单次 |
| 无关文件右键 | 菜单项仍在 | 选中项没有 PDF/文件夹时**自动隐藏**（`GetState` 过滤） |
| 需要 Python | 是 | 是（除非用 `-CliExe` 指向独立 exe） |
| 系统要求 | Win10/11 | Win11 21H2+（22000） |

## 安装（一台机器做一次）

前置：Windows 11 21H2+、Python（invoice-cli 已能用）、Windows SDK（makeappx/signtool，
装过 Visual Studio 或 Build Tools 一般就有）、Rust（只在本机首次构建时需要）。

```powershell
cd apps/explorer-extension/scripts
.\install.ps1          # 会弹一次 UAC: 把自签证书 CN=rename-invoice 导入 TrustedPeople
```

脚本会自动：构建 DLL → 写注册表 CLI 配置 → 生成自签证书 → `makeappx` 打包 →
`signtool` 签名 → `Add-AppxPackage -Register` 稀疏注册。

> 为什么要点"仍要运行此应用"？稀疏包必须签名。我们用本机生成的自签证书
> （`CN=rename-invoice`），证书只进你自己机器的 TrustedPeople，不对外分发。

## 卸载

```powershell
.\uninstall.ps1                  # 移除菜单 + CLI 注册表配置
.\uninstall.ps1 -RemoveCert      # 连自签证书一起清掉 (弹一次 UAC)
```

## 开发

```powershell
cargo build --release            # 产物: target/release/invoice_shext.dll
cargo clippy --release           # 提交前
```

- COM 类 GUID `{377B2F61-66A6-4688-A5BE-82AD42F3ADF6}` 固化在 `src/lib.rs` 与
  `package/AppxManifest.xml` 两处，**必须同步改**（改了等于逼所有用户重装）。
- 菜单标题/图标改在 `src/lib.rs` 的 `GetTitle` / `GetIcon`。
- 处理器路径存在 `HKCU\Software\rename-invoice\ExplorerExt`（`ExePath` + `Args`），
  DLL 启动失败时先查这里。

## 已知限制

- 只覆盖 Win11 现代菜单；经典菜单（"显示更多选项"里）仍由程序 1 的
  `install_context.bat` 负责，两者可共存。
- Windows 对稀疏包注册的菜单有缓存，新装后若菜单没出现，重启 explorer 或
  重开资源管理器窗口。
- 处理结果与程序 1 完全一致（同一 CLI、同一日志 `rename_invoice.log`）。
