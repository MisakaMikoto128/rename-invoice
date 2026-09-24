<p align="center">
<img src="./assets/icon.ico" alt="account-manager" width="96" height="96">
</p>

<h1 align="center">account-manager — 本地账目管理 (程序 2)</h1>

<p align="center">rename-invoice 的桌面 GUI：项目化管理报销批次，Flet 实现</p>

> 本程序是 [rename-invoice monorepo](../../README.md) 的三个程序之一。
> 跨报销批次跟踪发票（备注 / 淘宝单号 / 报销状态），发票提取复用
> [apps/cli](../cli/README.md) 的三层校验逻辑。

## 从 Release 下载（不需要 Python）

如果你只想用桌面 GUI 管理报销，**不需要任何编程环境**。

1. 打开 [GitHub Releases](https://github.com/MisakaMikoto128/rename-invoice/releases/latest)，下载 `AccountManager.exe`（约 106 MB）
2. 双击运行。第一次启动可能需要 5-10 秒（应用在解包）

> ⚠️ **Windows SmartScreen 警告**：第一次双击会弹"Windows 已保护你的电脑"。点 **更多信息** → **仍要运行** 即可——exe 没有购买代码签名证书，不是病毒。
>
> ⚠️ **杀毒软件误报**：个别杀毒软件会把 PyInstaller 打包的 exe 当成可疑程序。如有误报，请加白名单。

### 怎么用

启动后是一个 1200×720 的桌面窗口：

1. **新建项目** —— 主窗口左上角"+ 新建项目" → 输入项目名（比如"11月报销"）→ 自动创建文件夹
2. **导入 PDF** —— 进入项目 →"+ 导入 PDF"（或"导入文件夹"批量）→ 自动提取发票号 / 开票日期 / 销售方 / 金额，并按发票号去重
3. **编辑** —— 表格里点单元格直接改备注 / 淘宝单号 / 金额；状态下拉切换 未报销 / 报销中 / 已报销
4. **导出** ——"导出 xlsx"（带合计公式 + 人民币货币格式）/ "导出 zip"（打包 PDF + 可选 xlsx）

### 数据存哪里

- 数据库：`%APPDATA%\rename-invoice\accounts.db`（SQLite，单文件备份）
- 项目 PDF：`%APPDATA%\rename-invoice\projects\<项目名>\`（可在 ⚙️ 设置里把 PDF 存储位置迁移到任意路径，比如 D 盘或网盘同步文件夹）
- 设置：`%APPDATA%\rename-invoice\settings.json`

### 主要功能

- 项目化管理（每个报销批次 = 一个项目）+ 跨项目全局搜索
- 发票表格内编辑（备注 / 淘宝单号 / 金额 / 状态）+ 状态过滤 + 空白字段警告
- 项目 / 单张发票级联状态变更
- 项目回收站（删除可恢复，永久删除才真删）
- 导出 xlsx（合计公式）/ zip（打包 + 可选 Excel）
- 黑暗模式 / 窗口大小记忆 / PDF 存储位置可迁移
- 100% 离线，零联网

### 卸载

直接删除 exe + `%APPDATA%\rename-invoice\` 文件夹。注册表没有写入过任何项，无残留。

## 从源码运行

```bash
cd apps/account-manager
pip install -r requirements.txt   # flet + pymupdf + openpyxl
python -m accounting              # 启动 1200×720 桌面窗口
```

窗口布局：

- **主窗口**：左侧项目列表，右侧跨项目的报销状态统计（已报销 / 报销中 / 未报销 各多少张、总额）
- **项目详情**：点项目进入，上方是 PDF 列表，下方是可编辑表格（点单元格直接改备注 / 淘宝单号 / 金额等），右上角状态下拉切换报销状态

## 打包成 exe

见 [BUILD.md](./BUILD.md)（`python build.py`，产物约 75 MB 单文件）。

## 开发

```bash
pytest tests/    # 94 个单元测试 (db / services / UI state / extractor)
```

架构说明见仓库根 [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)。
