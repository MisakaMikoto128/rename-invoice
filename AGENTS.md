# rename-invoice — 项目现状速览

> 凡接手本项目的任务, 先读本文件顶部速览; 动手前扫「踩坑」条目。

## 功能地图 (三程序 monorepo)

| 程序 | 目录 | 技术 | 入口/用法 |
|---|---|---|---|
| invoice-cli (右键菜单小程序) | `apps/cli/` | Python 3.8+ (PyMuPDF) + **Rust 绿色版** `rust/` | 拖放/双击/经典右键; 核心是单文件 `rename_invoice.py` |
| account-manager (本地管理) | `apps/account-manager/` | Python + Flet + SQLite | `python -m accounting`; 打包见 `build.py` |
| explorer-extension (资源管理器插件) | `apps/explorer-extension/` | Rust + windows 0.62 (IExplorerCommand) | Win11 顶层右键; 安装 `scripts/install.ps1` |

- **核心校验逻辑唯一实现在 `apps/cli/rename_invoice.py`** — account-manager
  通过 `accounting/extractor.py` 动态 import 复用; explorer-extension 只 spawn
  不 import。改提取/校验逻辑只改这一处, 并同步 `test_parser.py`。
- 当前生产使用的右键菜单后端是 **Rust 版** `apps/cli/rust/release/` (verb 带
  `--silent --summary --xlsx`), Python 版是逻辑参考实现。
- 发版: 根 tag `vX.Y.Z`; explorer-extension 包版本另见
  `package/AppxManifest.xml` (需与签名路径一致)。

## 关键模式

- COM CLSID `{377B2F61-66A6-4688-A5BE-82AD42F3ADF6}` 固化在
  `src/lib.rs` + `package/AppxManifest.xml` **两处**, 必须同步。
- 右键菜单注册的是**绝对路径**: 移动仓库后必须重跑
  `apps/cli/install_context.bat`(经典) 或 explorer-extension `install.ps1`(Win11)。
- 所有含中文的 `.ps1` 必须 UTF-8 with BOM + CRLF (PS 5.1 兼容), CI 有检查。
- 稀疏 MSIX 注册: 开发者模式开启走 `Add-AppxPackage -Register -ExternalLocation`
  (免签名免 UAC); 未开则自签证书 + makeappx + signtool (弹一次 UAC)。
- windows-rs 的 `IExplorerCommand` 签名以 SDK 头文件 `shobjidl_core.h` 为准
  (`GetCanonicalName(GUID*)` / `GetFlags(EXPCMDFLAGS*)` 没有数组参数)。

## 踩坑 (历史教训, 勿重蹈)

- Git Bash 调 `makeappx/signtool` 会把 `/d` `/p` 转成路径 — 必须经 PowerShell 调。
- `git add -A` + 提前改 .gitignore 会误收二进制 (pdfium.dll 曾进过一次历史)。
- windows 0.58 与 0.62 的 `_Impl` trait 签名不同 (Option<&T> vs Ref<'_,T>,
  BOOL 位置, implement feature) — 升级需全文核对。
- Flet 0.85 API 迁移踩坑记录: `docs/dev/flet-0.85-gotchas.md`。

## 已知未修 (用户知情, 勿顺手修)

- 经典右键菜单 (程序1 verb) 在 Win11 藏在"显示更多选项"里 — 这是 explorer-extension
  (程序3) 存在的理由, 两者共存是设计而非 bug。
- 扫描件 (图片 PDF) 不支持 OCR — 有意为之 (可靠性优先), 见根 README FAQ。
- explorer-extension 依赖 Python 后端 (或 -CliExe 指定的独立 exe), 未内嵌
  pdfium 做重命名 — 保持 DLL 轻量是有意设计。
