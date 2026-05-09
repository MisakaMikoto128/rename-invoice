# account-manager — 设计文档

**版本**：v0.5.0（暂定）
**分支**：`feat/account-manager`
**日期**：2026-05-09

## 1. 目标

把 `rename-invoice` 从 CLI 工具升级出一个桌面 GUI——本地报销账目管理。
- 报销按"项目"（一个项目 = 一个文件夹）组织发票
- 项目里拖入 PDF → 自动提取字段 → 入库 → 在表格里编辑/搜索
- 跟踪报销状态（未/中/已），跨项目统计金额

不联网、不云、不付费。

## 2. 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 语言 | Python 3.10+ | 复用现有 PDF 提取逻辑；用户技术栈 |
| GUI | **Flet** | 单一 Python 语言；Material 3 自带，开箱美；桌面 + Web 同源代码 |
| 数据库 | **sqlite3 标准库 + 手写 SQL** | 不上 SQLAlchemy，避免 ORM 噪声；schema 几张表 |
| PDF 提取 | 复用 `rename_invoice.extract_invoice_metadata` | 已有三层校验，不重写 |
| 打包 | 暂不打包 | `python -m accounting` 跑得动就行；ship 阶段再考虑 PyInstaller |

**明确不上**：SQLAlchemy、Alembic、PyQt、Electron、Web 前端框架、ORM、依赖注入框架。

## 3. 表格"轻编辑"约定

- 点击单元格→编辑模式→Tab/Enter 切换→Esc 取消
- 状态列（项目状态、发票状态）用 Dropdown
- 金额列右对齐显示 `¥X.XX`
- **不做**：选区填充、复制粘贴多单元格、公式、单元格自定义格式

复杂编辑由 xlsx 导出环节承接（`rename_invoice.write_summary_xlsx` 已有）。

## 4. 数据模型

数据库文件：`%APPDATA%\rename-invoice\accounts.db`

```sql
CREATE TABLE project (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    folder_path  TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT '未报销'
                 CHECK(status IN ('未报销','报销中','已报销')),
    note         TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoice (
    id            INTEGER PRIMARY KEY,
    project_id    INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    file_name     TEXT NOT NULL,
    invoice_no    TEXT,
    invoice_date  TEXT,           -- '2025年11月18日' 原文; 排序用 ISO 格式存 YYYY-MM-DD
    invoice_date_iso TEXT,        -- 索引/排序专用
    seller        TEXT,
    amount        REAL,
    remark        TEXT,           -- 用户手填
    taobao_order  TEXT,           -- 用户手填
    status        TEXT NOT NULL DEFAULT '未报销'
                  CHECK(status IN ('未报销','报销中','已报销')),
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, file_name)
);

CREATE INDEX idx_invoice_project ON invoice(project_id);
CREATE INDEX idx_invoice_status  ON invoice(status);
CREATE INDEX idx_invoice_date    ON invoice(invoice_date_iso);
CREATE INDEX idx_invoice_seller  ON invoice(seller);
```

**项目状态和发票状态独立**——项目状态不自动派生于发票状态，由用户手动设置。原因：一个项目可能整批报销中，但其中几张已结清/几张被打回，状态不一一对应。

## 5. 模块结构

```
accounting/
├─ __init__.py
├─ __main__.py             # python -m accounting 启动
├─ db.py                   # 连接管理 + schema 初始化 + 简单迁移版本号
├─ models.py               # @dataclass Project, Invoice
├─ services/
│  ├─ project_service.py   # 项目 CRUD + 状态流转
│  └─ invoice_service.py   # 发票 CRUD + 导入 PDF + 搜索
├─ extractor.py            # 包装 rename_invoice.extract_invoice_metadata
├─ ui/
│  ├─ app.py               # Flet 入口 (ft.app)
│  ├─ main_view.py         # 顶级: 左侧项目列表 + 右侧总览
│  ├─ project_view.py      # 项目详情: 上 PDF 列表 + 下表格
│  ├─ stats_view.py        # 跨项目统计
│  └─ widgets/
│     ├─ status_chip.py
│     ├─ amount_text.py    # 统一 ¥X.XX 显示
│     └─ ...
└─ tests/                  # pytest, 主要 services 层
```

`accounting/` 与现有 `rename_invoice.py`（仍在 repo 根）**并存**，互不干扰。`extractor.py` 用 `from rename_invoice import extract_invoice_metadata` 导入，CLI 路径保持不变。

## 6. UI 草图

### 主窗口（项目列表 + 总览）
```
┌─────────────────────────────────────────────────────┐
│ rename-invoice / 账目管理                  [+ 新建] │
├──────────────┬──────────────────────────────────────┤
│ 项目列表      │ 跨项目统计                           │
│              │ ┌─────────────────────────────────┐ │
│ ▶ 11月报销    │ │ 已报销  ¥4,205.34   12 张      │ │
│   [报销中]    │ │ 报销中  ¥1,820.00    5 张      │ │
│              │ │ 未报销  ¥  823.50    3 张      │ │
│   10月差旅   │ │ ─────────────────────────────── │ │
│   [已报销]    │ │ 总计    ¥6,848.84   20 张      │ │
│              │ └─────────────────────────────────┘ │
│   [全部 5]   │                                      │
│              │ 按销售方分组 (Top 5):                │
│              │  • 苏州卡方    ¥1,205.34            │
│              │  • 顺丰        ¥  340.00            │
│              │  ...                                 │
└──────────────┴──────────────────────────────────────┘
```

### 项目详情
```
┌─────────────────────────────────────────────────────┐
│ ← 11月报销     [报销中 ▼]    [+导入PDF] [导出xlsx] │
├──────────────────────────────────────────────────────┤
│ [搜索: 销售方/号码/备注...]                          │
├─────────────┬────────────────────────────────────────┤
│ PDF 列表     │ 发票表格（点单元格编辑）              │
│              │  发票号  日期    销售方   ¥     状态  │
│ 📄 dzfp_25.. │  2595.. 11/18  深圳..  16.60 未▼   │
│ 📄 SO251..   │  2532.. 11/19  乐清..  19.68 中▼   │
│ 📄 顺丰..    │  ...                                  │
│ 📄 (拖入)    │                                       │
│              │  合计                  ¥X,XXX.XX     │
└─────────────┴────────────────────────────────────────┘
```

点 PDF 列表的某行 → 高亮表格里对应的发票（双向联动）。

## 7. 关键流程

### 7.1 创建项目
1. 点 `[+ 新建]` → 弹对话框：项目名 + 选/创建文件夹
2. INSERT project → 切到项目详情页
3. 文件夹存在已有 PDF：扫描并入库（同 7.2）

### 7.2 导入 PDF
1. 用户拖文件到 PDF 列表区，或点 `[+导入PDF]`
2. 把 PDF 复制到项目文件夹（不复制就直接用拖入路径？——**复制**，避免源文件被移动后失联）
3. 复用 `rename_invoice.extract_invoice_metadata(path)` 提取字段
4. （可选）先调用 `process_pdf` 给文件加价格前缀
5. INSERT invoice 行
6. 表格新增一行

### 7.3 编辑 / 状态流转
- 点表格单元格 → Flet 把 Text 替换成 TextField → Tab/Enter 提交 → 调 `invoice_service.update_field` → UPDATE 写库
- 状态用 ft.Dropdown，change 事件直接写库
- 项目状态在 header 的 Dropdown 改

### 7.4 搜索
- 单一搜索框，模糊匹配 `invoice_no | seller | remark | taobao_order`
- 服务端：`WHERE invoice_no LIKE ? OR seller LIKE ? OR ...`
- 表格只显示匹配行

### 7.5 跨项目统计
启动 / 切到主窗口时：
```sql
SELECT status, COUNT(*), COALESCE(SUM(amount), 0)
FROM invoice GROUP BY status;

-- 或按项目维度
SELECT p.status, COUNT(*), COALESCE(SUM(i.amount), 0)
FROM project p LEFT JOIN invoice i ON i.project_id = p.id
GROUP BY p.status;
```

UI 给两个切换按钮：[发票维度] / [项目维度]。

### 7.6 导出 xlsx
项目页 `[导出xlsx]` → 调 `rename_invoice.write_summary_xlsx(...)` → 直接复用现有逻辑，零代码新增。

## 8. 开发里程碑（建议三步走，每步一个可用 demo）

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| **M1 数据 + 服务层** | db.py / models / services / 单测 | `pytest` 全绿，能 CRUD project / invoice |
| **M2 项目页可用** | 主窗口、项目页、PDF 导入、表格编辑、状态流转 | 拖入 PDF → 看到字段 → 编辑保存 → 重启数据还在 |
| **M3 统计 + 搜索** | 跨项目统计页、搜索框、xlsx 导出 | 能切发票/项目维度看总额，搜索过滤生效 |

每个 M 一个 PR 合到 `feat/account-manager`，全部完成后再合 main 发 v1.0。

## 9. 明确不做（YAGNI）

- 多用户 / 云同步 / 服务器
- 数据库迁移框架（schema 改了就直接改 SQL，加版本号判断）
- 公式 / 选区填充 / 复制粘贴多格
- PDF 内容预览（用户可以双击 PDF 用系统默认应用打开，够用）
- 报销状态自动派生 / 工作流引擎
- 发票去重（同一文件再导入会被 UNIQUE 约束拦下，足够）
- OCR 扫描件支持
- 国际化 i18n（只做中文）

## 10. 风险 / 未决

- **Flet 的 DataTable 内嵌编辑**实现起来要不要包一层 widget？先按 M1 完了实测一行编辑，不行再看 PlutoGrid 之类
- **PDF 拖放**到 Flet：`ft.FilePicker` 是显式选择，拖放需要看 Flet 0.x 的桌面平台是否支持原生 drop target；如果不行，回退到 `[+ 导入]` 按钮 + 文件选择器
- **数据库位置**`%APPDATA%` 路径在 Linux/Mac 上不同——但项目目标是 Windows-only，用 `os.environ['APPDATA']` 直接读
