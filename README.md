<p align="center">
<img src="./assets/icon-256.png" alt="rename-invoice" width="128" height="128">
</p>

<h1 align="center">rename-invoice</h1>

<p align="center">中国增值税电子发票工具箱 — 三个程序, 一套校验逻辑</p>

<p align="center">
<a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
<img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg" alt="Platform: Windows">
<a href="./CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.1.0-green.svg" alt="Version 1.1.0"></a>
</p>

把中国大陆增值税电子发票 PDF 重命名成 `{价税合计}元-{原文件名}.pdf`, 方便报销时一眼看到金额。

```text
某某科技有限公司_20260416104223.pdf
        ↓
98.01元-某某科技有限公司_20260416104223.pdf
```

**面向财务场景: 金额错认会引发实际损失。工具采用三层校验
(中文大写 ↔ 阿拉伯数字精确匹配 + 最大 ¥ 值检查 + 失败即拒绝),
任一不通过就不重命名, 绝不猜测。** 100% 离线, 零联网。

> A Windows toolbox that renames Chinese VAT invoice PDFs to include their
> total amount as a filename prefix, with strict cross-validation between the
> numeric amount and the Chinese uppercase amount. Useful for reimbursement.

## 三个程序

| # | 程序 | 目录 | 技术 | 一句话 |
|---|---|---|---|---|
| 1 | **invoice-cli** 右键菜单小程序 | [`apps/cli`](./apps/cli/) | Python + PyMuPDF | 拖放 / 双击 / 经典右键菜单, 三层校验的核心实现 |
| 2 | **account-manager** 本地账目管理 | [`apps/account-manager`](./apps/account-manager/) | Python + Flet + SQLite | 项目化管理报销批次, 表格编辑, 导出 xlsx/zip |
| 3 | **explorer-extension** 资源管理器插件 | [`apps/explorer-extension`](./apps/explorer-extension/) | Rust + COM (IExplorerCommand) | Win11 **顶层**右键菜单直达, 带图标, 多选单次触发 |

三个程序共享同一套发票提取/校验逻辑 (apps/cli/rename_invoice.py),
处理结果完全一致, 审计日志同一份。

## 快速开始

**只是想给发票改名?** → 程序 1:

```bash
cd apps/cli
pip install -r requirements.txt
python rename_invoice.py "D:\报销文件夹"     # 或双击 rename_invoice.bat
.\install_context.bat                        # (可选) 注册经典右键菜单
```

**想跨批次管理报销?** → 程序 2 (免 Python 的 exe 见 [Releases](https://github.com/MisakaMikoto128/rename-invoice/releases)):

```bash
cd apps/account-manager
pip install -r requirements.txt
python -m accounting
```

**用 Windows 11 新版右键菜单?** → 程序 3 (需要 Rust + Windows SDK):

```powershell
cd apps\explorer-extension\scripts
.\install.ps1          # 完成后右键任意 PDF / 文件夹, 菜单顶层出现"添加发票价格前缀"
```

详细用法、截图示例、FAQ 见各程序目录的 README。

## 选择哪个入口?

| 场景 | 推荐 |
|---|---|
| 偶尔处理一批发票, 用完即走 | 程序 1 (拖放 / 右键) |
| Win11, 想要最顺手的一键处理 | 程序 3 (顶层右键菜单) |
| 管理整月报销, 要填备注/淘宝单号/报销状态 | 程序 2 |
| 老板要 Excel 汇总 | 程序 1 `--xlsx` 或程序 2 导出 |

## 仓库结构

```text
rename-invoice/
├─ apps/
│  ├─ cli/                   # 程序1: rename_invoice.py + 右键菜单注册脚本
│  ├─ account-manager/       # 程序2: Flet GUI + SQLite + 打包脚本
│  └─ explorer-extension/    # 程序3: Rust COM DLL + 稀疏 MSIX + 安装脚本
├─ assets/                   # 共享图标 (生成脚本可重现)
├─ docs/                     # 设计文档 / 架构 / 踩坑记录
├─ tools/                    # shell-ext-manager.ps1 等辅助工具
├─ .github/                  # CI (Python + Rust), issue/PR 模板
├─ CHANGELOG.md
├─ CONTRIBUTING.md
└─ SECURITY.md
```

## 可靠性是怎么保证的

每张增值税发票都有两个法律等价的金额字段: 价税合计(小写) `¥98.01`
和 价税合计(大写) `玖拾捌圆零壹分`。工具同时提取两者, 要求精确匹配
(容差 0.005 元), 且大写转换值必须是全票最大 ¥ 值 (防止错认金额/税额行)。
任何一步不确定 → 保留原名 + 记审计日志。中文大写解析器有 15 个单元测试,
全部业务逻辑 109 个测试由 CI 在 Windows 上跑。

## 贡献

欢迎 issue 和 PR。提交前请跑:

```bash
cd apps/cli               && python test_parser.py
cd apps/account-manager   && pytest tests/
cd apps/explorer-extension && cargo clippy --release
```

约定见 [CONTRIBUTING.md](./CONTRIBUTING.md)。发票样本无法识别? 欢迎在 issue
里提供**脱敏后的**样本 (公司名、号码可涂黑, 金额字段保留)。

## 致谢

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) — PDF 文本提取
- [Flet](https://flet.dev/) — Python 桌面 GUI
- [windows-rs](https://github.com/microsoft/windows-rs) — Rust COM/Win32 绑定

## 许可

MIT License - 详见 [LICENSE](./LICENSE)。

> 免责声明：本工具尽最大努力保证金额提取准确，但不对因使用本工具产生的任何财务后果负责。报销前请自行核对金额。
