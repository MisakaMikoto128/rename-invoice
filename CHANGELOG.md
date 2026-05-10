# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.5.3] - 2026-05-10

### Added (account-manager GUI)

- **状态过滤 chips**：表格上方 `全部(N) / 未报销(N) / 报销中(N) / 已报销(N)` 按钮，点击切换过滤；与搜索可叠加
- **导入整个文件夹**：项目页 "导入文件夹" 按钮，扫描目录所有 PDF 一键导入（同样自动加前缀 + 按发票号去重）
- **手动添加发票（无 PDF）**：项目页 "手动添加" 按钮，对话框填字段直接入库；行的"文件"列显示 `[手动] xxx`
- **空白字段视觉警告**：备注 OR 淘宝单号空着的行整行底色变浅黄 `#FFF8E1`
- **窗口大小记忆**：关闭时记下宽高/位置/最大化状态到 settings.json，重开还原

## [0.5.2] - 2026-05-10

### Added (account-manager GUI)

- **全局跨项目搜索**：主窗口顶部搜索框，输入即过滤，结果列表显示项目名 + 发票详情；点击结果直接跳进对应项目并预过滤到该行
- **仓库根目录迁移**：⚙️ 设置对话框可把 `%APPDATA%\rename-invoice\projects` 整体移到任意位置（DB 仍在原位），DB 内每个项目的 folder_path 自动更新
- **PDF 另存为**：项目内 PDF 列表每行 💾 图标，单击复制到任意位置（记住上次目录）
- **黑暗模式切换**：设置对话框里的开关，写入 settings.json，启动时自动恢复
- **项目回收站**（含 schema 迁移 v1→v2）：
  - 主页 🗑 改为软删除（移到回收站），SnackBar 显示"[撤销]"按钮 5 秒可点
  - 主页右上 "回收站 (N)" 入口
  - 回收站页：列出所有已删除项目（带删除时间）+ "恢复" / "永久删除" 两按钮
  - 永久删除才真删 DB（CASCADE 删发票），PDF 文件始终保留

### Changed

- `delete_project` 服务保持原语义（硬删，CASCADE）；新增 `trash_project` / `restore_project` / `list_trashed_projects`
- `list_projects` / `get_project` 默认过滤 `deleted_at IS NULL`
- DB schema 自动从 v1 ALTER 升到 v2（加 `deleted_at` 列），老 DB 无感升级

### Fixed

- Flet 0.85 `TextButton` 不接受 `text=` kwarg，改成位置参数
- Flet 0.85 `page.run_task` 需要 coroutine function + args 分开传，不是返回 coroutine 的 sync lambda

## [0.5.1] - 2026-05-10

### Added (account-manager GUI 小补丁)

- **删除项目**：主页项目列表每行有 🗑 按钮 + 确认对话框（仅删 DB 记录，PDF 文件保留）
- **改项目名**：项目页标题旁 ✏️ 按钮（项目文件夹名不会跟着改）
- **单击 PDF 打开**：项目内 PDF 列表点任意一行 → 系统默认 PDF 阅读器打开（`os.startfile`）
- **删除单张发票**：表格每行末尾 🗑 + 确认对话框（仅删 DB 记录，PDF 文件保留）
- **新对话框 helper** `show_confirm_dialog`（红色确认按钮通用模式）

## [0.5.0] - 2026-05-10

### Added

CLI 工具之外**新增桌面 GUI**——本地报销账目管理（`python -m accounting.ui.app`）：

- **新 Python 包 `accounting/`**：sqlite3 数据层 + 服务层 + Flet UI 三层架构，77 个单测
- **项目化管理**：每个报销批次 = 一个项目，自动建文件夹于 `%APPDATA%\rename-invoice\projects\<项目名>\`
- **Flet 桌面窗口**（1200×720，Material 3）：
  - 主窗口：左侧项目列表 + 右侧跨项目报销状态统计（金额 + 张数）
  - 项目详情：上方 PDF 列表 + 下方可编辑表格 8 列（文件 / 发票号 / 日期 / 销售方 / 备注 / 淘宝单号 / 金额 / 状态）
  - 表格水平滚动 / 实时搜索（不丢焦点）/ 单元格点击编辑 / 状态下拉
- **导入 PDF**：通过文件选择器（OS 拖放在 Flet 0.85 暂不支持），自动重命名加 `XX元-` 前缀，按发票号在项目内去重
- **导出 xlsx**：复用 CLI 模式的 `write_summary_xlsx`，默认文件名 `<总额>元-<项目名>_发票汇总.xlsx`
- **导出 zip**：打包项目内 PDF，可选附带 Excel 汇总，可选总价格前缀（默认 ON）
- **项目状态级联**：改项目状态下拉同步更新项目下所有发票状态
- **记住上次目录**：导入/导出/zip 三个文件选择器各自记住上次路径，存 `%APPDATA%\rename-invoice\settings.json`
- **数据库** `%APPDATA%\rename-invoice\accounts.db` —— SQLite 单文件，方便备份

### Notes

- CLI 工具（重命名/Excel 汇总/右键菜单）原样保留，所有 CLI 行为不变
- GUI 是**可选**，仅在你需要跨批次跟踪报销时有用

## [0.4.0] - 2026-05-09

### Changed

- `install_context.bat` 安装交互改成**两个独立 y/n 问题**（汇总窗口? Excel 汇总?）取代原先的"三选一"，现在四种组合都支持（包括"窗口+Excel"两个都开）
- Excel 金额列从纯数字 `0.00` 改成**人民币货币格式** `¥#,##0.00`（千分位 + 两位小数 + 负数红色），合计行同样格式
- `install_context.ps1` 命令行参数：移除 `-NoSummary`，新增 `-NoPrompt`；`-Summary` 和 `-Xlsx` 改为可独立组合（**breaking change for scripted use**）

## [0.3.0] - 2026-05-09

### Added

- **Excel 汇总导出**：右键安装时新增 `[3]` 模式，处理完后在目标文件夹生成 `发票汇总_YYYYMMDD-HHMMSS.xlsx`
- 表头：发票文件名称 / 发票号码 / 开票日期 / 销售方名称 / 备注名称（留空手填）/ 淘宝单号（留空手填）/ 金额
- 末尾合计行使用 `=SUM(G2:Gn)` 公式（不是硬编码值，改任一金额能自动重算）
- 表头粗体白字蓝底、合计行黄底加粗、首行冻结、列宽预设
- 字段提取支持两种发票布局：
  - 旧版（label 在前 / value 在后，独立行的 20 位发票号码）
  - 新版（"发票号码: 数字" 同行；销售方名称用首页坐标判断，水平中点 > 页面中线者为销售方）
- `--xlsx` 命令行 flag（可与 `--silent` 任意组合，也支持直接模式）
- `install_context.ps1` 加 `-Xlsx` switch（脚本化使用）
- `requirements.txt` 加 `openpyxl>=3.1.0` 依赖

### Changed

- `process_pdf` 返回值从 `(status, message)` 扩展为 `(status, message, metadata, final_path)`，metadata 同时供重命名和 Excel 用，避免重复读 PDF

## [0.2.0] - 2026-05-08

### Added

- 右键菜单改为默认静默 (pythonw.exe) — 完全无 cmd 窗口闪烁
- 文件锁 + 队列架构：多选 N 个 PDF 触发 N 次右键 → 1 个 leader 进程统一处理 → 1 条日志批次（解决"开 N 条线程"的浪费）
- `--silent` 命令行标志：静默 + 队列模式
- `--summary` 命令行标志：处理完后弹 Tk 汇总窗口（列出成功/跳过/失败明细）
- `install_context.ps1` 安装时交互选择：[1] 静默（默认） / [2] 静默 + 汇总窗口
- `install_context.ps1` 加 `-Summary` / `-NoSummary` 命令行 switch（脚本化使用）

### Changed

- 右键菜单注册的命令从 `rename_invoice.bat` 改为直接调 `pythonw.exe rename_invoice.py --silent`
- 双击 `.bat` / 拖放到 `.bat` 这两个路径不变，仍然在 cmd 窗口显示彩色输出

## [0.1.0] - 2026-04-28

### Added

- 核心脚本 `rename_invoice.py`：从增值税电子发票 PDF 提取价税合计，重命名为 `{金额}元-{原文件名}.pdf`
- 中文大写金额解析器（壹贰叁…玖、拾佰仟万亿、圆角分整），含 15 个单元测试
- 三层财务可靠性校验：
  - 中文大写金额转数字 = PDF 中某 ¥ 值
  - 该 ¥ 值必须是文档最大值（价税合计 ≥ 金额、税额）
  - 任一失败拒绝重命名，原文件保持不动
- 三种使用方式：
  - 拖放（PDF 文件或文件夹拖到 `rename_invoice.bat`）
  - 双击当前目录扫描
  - Windows 资源管理器右键菜单（HKCU 注册，无需管理员）
- 一次性右键菜单注册：`install_context.bat` / `uninstall_context.bat`
- 幂等：已加价格前缀的文件（匹配 `^\d+(\.\d{1,2})?元-`）自动跳过
- 重名安全：目标文件已存在时追加 `(2)`、`(3)`，绝不覆盖
- 审计日志：所有重命名/失败追加到 `rename_invoice.log`
- 项目图标（深蓝圆角 + 白色 ¥），多尺寸 `.ico`（16/24/32/48/64/128/256），右键菜单自动应用
- 可重现的图标生成脚本 `assets/generate_icon.py`
- 开源项目标配：`LICENSE`(MIT) / `CHANGELOG.md` / `CONTRIBUTING.md` / `SECURITY.md`
- GitHub Issue / PR 模板（`.github/ISSUE_TEMPLATE/*` + `PULL_REQUEST_TEMPLATE.md`）
- GitHub Actions CI：Windows + Python 3.8/3.11/3.12 跑单元测试 + 强制 `.ps1` 文件 UTF-8 BOM 检查

### Fixed

- `install_context.ps1` 因 PS 5.1 按 ANSI 误读 UTF-8 中文字符而无法运行 —— 强制 .ps1 文件保存为 UTF-8 with BOM
- `uninstall_context.ps1` 中文输出乱码 —— 同上修复
