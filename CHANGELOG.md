# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
