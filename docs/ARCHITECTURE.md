# 架构总览

三个程序 + 一份共享的发票解析核心。本文说明它们怎么组织、怎么协作、为什么这么设计。

## 拓扑

```text
                    ┌────────────────────────────────────┐
                    │  apps/cli/rename_invoice.py        │
                    │  (三层金额校验的唯一实现)            │
                    │  extract_invoice_metadata()        │
                    │  chinese_amount_to_decimal()       │
                    └────────▲──────────▲────────────────┘
                             │ import    │ spawn (pythonw --silent)
        ┌────────────────────┴──┐     ┌──┴─────────────────────────┐
        │ apps/account-manager  │     │ apps/explorer-extension    │
        │ (Flet GUI, 程序 2)    │     │ (Rust COM DLL, 程序 3)     │
        │ accounting/extractor  │     │ invoice_shext.dll          │
        │ .py 动态 import       │     │ IExplorerCommand::Invoke   │
        └───────────────────────┘     └────────────────────────────┘
                             ▲
                             │ 直接调用 (拖放/双击/经典右键 verb)
                    ┌────────┴───────────┐
                    │ 用户 / 脚本         │  ← 程序 1 自己就是入口
                    └────────────────────┘
```

## 各程序职责边界

### apps/cli (程序 1) — 核心 + 经典入口

- `rename_invoice.py` 是**单文件自包含脚本**: 解析、校验、重命名、队列、审计日志、
  xlsx 导出全在里面。它不是 package, 其它程序通过 `sys.path` 注入复用它。
- 经典右键菜单走 HKCU 注册表 verb (`install_context.ps1`), 多选时 N 次进程
  通过文件锁 (`.leader.lock` + `msvcrt.locking`) 合并为一次处理。
- 为什么单文件：右键菜单注册的是绝对路径，单文件 = 部署面最小；也是 GUI
  frozen 打包时唯一的 data 文件 (`build.py --add-data`)。

### apps/account-manager (程序 2) — GUI

- Flet + SQLite (`%APPDATA%\rename-invoice\accounts.db`)。
- `accounting/extractor.py` 是唯一跨程序耦合点: dev 模式把 `apps/cli` 加进
  `sys.path` 后 `import rename_invoice`; frozen 模式从 `sys._MEIPASS` 拿
  (build.py 已把 rename_invoice.py 打进包)。
- 测试 `tests/` 94 个，覆盖 db/services/ui state/extractor。

### apps/explorer-extension (程序 3) — Win11 现代菜单

- Rust cdylib, 零运行时依赖 (只有 windows-core/windows)。
- `IExplorerCommand` 是 Windows 11 现代右键菜单的官方扩展点。Explorer 会:
  1. 对选中项集合调 `GetState` → 没有目标 (PDF/文件夹) 时返回 `ECS_HIDDEN`
  2. 展开菜单时调 `GetTitle`/`GetIcon`/`GetToolTip`
  3. 用户点击时调 `Invoke` → **一次拿到全部选中路径**, 交给 CLI
- DLL 不做任何业务逻辑：读 `HKCU\Software\rename-invoice\ExplorerExt` 的
  `ExePath`/`Args`, 追加选中路径后 spawn。默认指向 pythonw + 程序 1。
- 注册用**稀疏 MSIX 包** (`package/AppxManifest.xml`):
  - `com:ComServer/com:Class` 声明 COM 类 (CLSID 固化)
  - `desktop4:FileExplorerContextMenus` 挂三个 ItemType (`*`/`Directory`/
    `Directory\Background`)
  - `uap10:AllowExternalContent=true` → DLL/exe 留在源码树，不复制进系统
  - 开发者模式开启时 `Add-AppxPackage -Register` 直注册 (免签名免 UAC);
    否则走自签证书 + signtool + TrustedPeople (弹一次 UAC)

## 版本与发布

- 根 tag `vX.Y.Z` 面向 Python 侧 (CLI + GUI), SemVer。
- 程序 3 的包版本在 `package/AppxManifest.xml` 的 `Version`, 发版时同步。
- CI (`.github/workflows/test.yml`): Windows runner 上跑两套 Python 测试 +
  `cargo build`。

## 已知约束

- explorer-extension 只进 Win11 21H2+ 的**现代**菜单；经典菜单 ("显示更多
  选项"里) 由程序 1 的 verb 负责，两者共存。
- 稀疏包的 InstallLocation 指向源码树 → 移动仓库目录后需重跑
  `scripts/install.ps1` (与程序 1 的右键菜单注册同样的限制)。
- CLSID `{377B2F61-66A6-4688-A5BE-82AD42F3ADF6}` 固化在 lib.rs 与
  AppxManifest.xml 两处，改了必须同步，等于逼所有用户重装。
- windows-rs 的 `IExplorerCommand` 签名以 SDK 头文件 `shobjidl_core.h` 为准
  (`GetCanonicalName(GUID*)` / `GetFlags(EXPCMDFLAGS*)` 没有数组参数)。
