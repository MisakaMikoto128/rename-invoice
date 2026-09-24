<p align="center">
<img src="./assets/icon.ico" alt="invoice-cli" width="96" height="96">
</p>

<h1 align="center">invoice-cli — 右键菜单小程序 (程序 1)</h1>

<p align="center">rename-invoice 的 CLI 入口：拖放 / 双击 / Windows 经典右键菜单</p>

> 本程序是 [rename-invoice monorepo](../../README.md) 的三个程序之一。
> 负责把增值税发票 PDF 重命名为 `{价税合计}元-{原文件名}.pdf`,
> 是全部三层金额校验逻辑的唯一实现 (account-manager 与 explorer-extension 都复用它)。

本目录含两个实现:

- **Python 版** (`rename_invoice.py`, 本 README 主体) — 源码参考实现，逻辑唯一权威
- **Rust 绿色版** ([rust/](./rust/README.md)) — 单 exe + pdfium.dll, 无需 Python,
  拖放/右键/双击行为与 Python 版对齐 (Slint 汇总窗口), 是日常使用的发行版

## 特性

- ✅ 三层财务校验：中文大写↔阿拉伯数字精确匹配 + 最大 ¥ 值检查
- ✅ 三种使用方式：拖放、双击、Windows 右键菜单
- ✅ 右键菜单**默认全静默**（零 cmd 窗口闪烁），多选 N 个 PDF 通过文件锁合并为单次处理
- ✅ 可选 **Excel 汇总**：处理完后在文件夹生成 `发票汇总_<时间戳>.xlsx`（发票号/日期/销售方/金额 + 合计公式 + 人民币货币格式）
- ✅ 可选 **Tk 汇总窗口**：处理完弹一个窗口列出本批结果（成功/跳过/失败）
- ✅ 幂等可重跑：已加前缀的文件自动跳过
- ✅ 失败安全：任何不确定就保留原名 + 红色高亮 + 审计日志
- ✅ 不需要管理员权限（HKCU 注册右键菜单）
- ✅ 100% 离线，不上传任何数据

## 安装

```bash
git clone https://github.com/MisakaMikoto128/rename-invoice.git
cd rename-invoice/apps/cli
pip install -r requirements.txt   # pymupdf + openpyxl
# (可选) 注册 Windows 经典右键菜单
.\install_context.bat
```

需要 Windows 10/11 + Python 3.8+。详见 [初次安装](#初次安装) 章节。


---

## 目录

- [一分钟上手](#一分钟上手)
- [初次安装](#初次安装)
- [三种使用方式](#三种使用方式)
- [可靠性是怎么保证的](#可靠性是怎么保证的)
- [失败时怎么办](#失败时怎么办)
- [审计日志](#审计日志)
- [文件清单](#文件清单)
- [故障排查](#故障排查)
- [更新和卸载](#更新和卸载)
- [常见问题](#常见问题)


---

## 一分钟上手

```text
1. 把 rename_invoice.bat 复制到当前报销文件夹（或者放快捷方式）
2. 双击它
3. 看输出，按回车关闭
4. 完成
```

如果你想要右键菜单更方便，**只需要一次性**双击 `install_context.bat`。


---

## 初次安装

### 前提条件

- Windows 10 / 11
- Python 3.8+ 已安装并在 PATH 里
- 依赖库：`pymupdf`（PDF 解析）、`openpyxl`（Excel 汇总，可选不用就不会触发）

### 检查环境

打开任意命令行（cmd / PowerShell / Git Bash），运行：

```bash
python --version
python -c "import fitz, openpyxl; print('OK')"
```

如果报缺包：

```bash
pip install -r requirements.txt
```

### 工具的安装位置

仓库克隆到哪儿，工具就在哪儿（脚本位于仓库的 `apps/cli/` 下），例如本机当前是
`C:\Users\<用户名>\tools\rename_invoice\apps\cli\`。

> **不要随意挪动这个目录**——右键菜单的注册表指向绝对路径。如果一定要挪：
>
> 1. 先双击 `uninstall_context.bat`（卸载旧的右键菜单）
> 2. 再挪动整个仓库
> 3. 最后双击新位置 `apps/cli/` 下的 `install_context.bat`（重新注册）

### （可选）注册右键菜单

只需要做**一次**：

1. 双击 `apps/cli/install_context.bat`
2. 回答两个独立问题（回车=否）：
   - **是否处理完后弹出 Tk 汇总窗口？** `[y/N]`（一个小窗口列出本批全部成功/跳过/失败）
   - **是否处理完后在文件夹生成 Excel 汇总？** `[y/N]`（生成 `发票汇总_<时间戳>.xlsx`）
3. 看到三行 `[OK]` 即成功，按回车关闭

四种组合都支持：

|选择 |行为 |
|---|---|
|N + N |纯静默，结果只写日志（推荐默认） |
|Y + N |静默 + Tk 汇总窗口 |
|N + Y |静默 + Excel 汇总 |
|Y + Y |静默 + Tk 窗口 + Excel 汇总（窗口里也会列出 xlsx 路径） |

之后无论在哪个文件夹/PDF 上右键，都会出现 **"添加发票价格前缀"**。想换组合就再双击一次 `install_context.bat`。

> ⚠️ Windows 11 用户可能要点 **"显示更多选项"**（或按 `Shift + F10`）才能看到这个菜单。

> 💡 多选 N 个 PDF 右键时，Windows 会触发 N 次菜单调用，但工具用文件锁合并成一次处理：你只会看到一条日志批次（启用汇总窗口时也只弹一个窗口）。


---

## 三种使用方式

### 方式 A：拖放

把 PDF 文件或者整个文件夹**拖**到 `rename_invoice.bat` 上。

- 拖单个 PDF → 处理这一个文件
- 拖一个文件夹 → 处理该文件夹下所有 `*.pdf`（不递归子目录）
- 拖多个 → 全都处理

支持中文路径、空格路径。

### 方式 B：右键菜单

需要先做一次 [注册右键菜单](#可选注册右键菜单)。

|在哪儿右键 |做什么 |
|---|---|
|任意 PDF 文件（可多选） |处理选中的 PDF |
|任意文件夹（图标上） |处理该文件夹下所有 PDF |
|任意文件夹空白处（资源管理器内） |处理当前打开的文件夹下所有 PDF |

右键路径**默认静默**：不弹任何窗口，结果只写到 `rename_invoice.log`。安装时可独立开启：

- **汇总窗口**：处理完弹一个 Tk 窗口列出本批全部成功/跳过/失败
- **Excel 汇总**：处理完在当前文件夹生成 `发票汇总_YYYYMMDD-HHMMSS.xlsx`，含发票号码/开票日期/销售方/金额（人民币货币格式 ¥X.XX），末尾合计 `=SUM(...)` 公式

两个开关独立，可以全开、全关、或只开一个。备注名称和淘宝单号两列留空给你手填。

### 方式 C：双击当前目录

把 `rename_invoice.bat` 复制（或快捷方式）到当前报销文件夹，**双击**它。

- 自动扫描脚本所在目录下所有 PDF
- 已经有 `XX元-` 前缀的文件**自动跳过**（幂等：重复双击没副作用）

> 小技巧：把 `rename_invoice.bat` 的快捷方式放到桌面或常用报销根目录，需要时拖进当前批次文件夹再双击。

### 命令行（高级用户）

```bash
# 在本目录 (apps/cli) 下执行:
python rename_invoice.py "D:\path\to\folder"
python rename_invoice.py "D:\path\to\file.pdf"
python rename_invoice.py "D:\folder1" "D:\folder2"

# 静默 + 队列模式 (右键菜单走的就是这个; 一般不用直接调用)
pythonw rename_invoice.py --silent "D:\path"

# 静默 + 处理完弹 Tk 汇总窗口
pythonw rename_invoice.py --silent --summary "D:\path"

# 静默 + 处理完导出 Excel 汇总到目标文件夹
pythonw rename_invoice.py --silent --xlsx "D:\path"
```

无参数时扫描当前工作目录。


---

## 可靠性是怎么保证的

财务文件容不得错（98.01 错认成 980.10 就是事故），工具用三层校验：

### 第 1 层：双重金额一致性

每张增值税发票必有两个**法律等价**的金额字段：

|字段 |形态 |例 |
|---|---|---|
|价税合计（小写） |阿拉伯数字 |`¥98.01` |
|价税合计（大写） |中文金额 |`玖拾捌圆零壹分` |

工具会：

1. 用正则 `¥\d+(\.\d{1,2})?` 找出 PDF 里所有候选小写金额
2. 用字符集匹配找出中文大写金额（含 `圆/元` 字）
3. 调用 `chinese_amount_to_decimal()` 把大写转成数字
4. **必须**存在某个 ¥ 值精确等于（容差 0.005 元）大写转换值

转换器对常见格式都做了单元测试，包括：
`玖拾捌圆零壹分`(98.01)、`壹仟贰佰叁拾肆圆伍角陆分`(1234.56)、`壹佰零伍圆整`(105.00)、`壹万贰仟叁佰肆拾伍圆陆角柒分`(12345.67)、`壹亿圆整`(100000000.00) 等 15 个用例。

### 第 2 层：最大值检查

价税合计 = 金额 + 税额，所以必然是发票上**最大**的 ¥ 值。

如果中文大写转换出来的数字不是最大 ¥ 值，工具拒绝重命名（说明可能错认到了"金额"或"税额"行）。

### 第 3 层：失败安全

任何一步失败：

- 大写金额找不到 → 失败
- 大写无法解析 → 失败
- 没有 ¥ 数字 → 失败
- ¥ 数字与大写不匹配 → 失败
- 大写转换值不是最大 ¥ → 失败
- 文件已经有 `XX元-` 前缀 → **跳过**（不算失败）
- 目标文件名已存在 → 自动追加 `(2)`、`(3)`，绝不覆盖

失败的文件**保持原文件名不动**，控制台用红色 `[FAIL]` 高亮，并附错误原因。


---

## 失败时怎么办

工具运行结束会列出所有失败：

```text
重命名: 3  跳过: 1  失败: 1

以下文件需手动处理:
  - 某发票.pdf
      原因: 中文大写金额与 ¥ 值不匹配. 中文: [...], ¥ 值: [86.73, 11.28]
```

可能的原因和处理：

|失败原因 |含义 |处理 |
|---|---|---|
|`PDF 无文字层 (可能是扫描件)` |PDF 是图片扫描的，没文字 |用 OCR 工具先转成可搜索 PDF；或手动改名 |
|`未找到中文大写金额` |不是发票，或格式特殊 |检查是不是真的发票文件 |
|`未找到 ¥ 价格标记` |同上 |同上 |
|`中文大写金额与 ¥ 值不匹配` |PDF 文本提取乱了，或非标准格式 |用 PDF 阅读器打开看看，手动改名 |
|`中文大写金额不是最大 ¥ 值` |提取到的中文金额可能错认 |用 PDF 阅读器对照后手动改名 |
|`重命名失败` |文件被占用（被其他程序打开） |关闭 PDF 阅读器再试 |

> 💡 失败的文件**没有被改动**，可以放心检查。


---

## 审计日志

每次成功或失败都会追加记录到：

```text
<仓库>\apps\cli\rename_invoice.log    (即脚本同目录)
```

格式：

```text
[2026-04-28 15:02:26] OK    原文件名.pdf  ->  98.01元-原文件名.pdf  (金额=98.01)
[2026-04-28 15:02:30] FAIL  某文件.pdf  原因: 中文大写金额与 ¥ 值不匹配. ...
[2026-05-08 16:11:02] SKIP  98.01元-某发票.pdf  (已有价格前缀, 跳过)
[2026-05-08 16:11:02] XLSX  导出 -> D:\报销\发票汇总_20260508-161102.xlsx  (6 行)
```

需要时可以用日志反查或回滚。日志只追加不清空，体积不会爆炸（每行约 200 字节，1 万次操作约 2MB）。


---

## 文件清单

```text
apps/cli/
├─ rename_invoice.py          # 核心脚本 (三层校验逻辑的唯一实现)
├─ rename_invoice.bat         # 拖放/双击入口
├─ rename_invoice.log         # 审计日志（运行后自动生成, 不入库）
├─ install_context.bat/.ps1   # 注册经典右键菜单
├─ uninstall_context.bat/.ps1 # 卸载经典右键菜单
├─ test_parser.py             # 中文大写金额解析单元测试 (15 例)
├─ requirements.txt           # Python 依赖 (pymupdf + openpyxl)
├─ assets/icon.ico            # 多尺寸图标（16~256）
└─ rust/                      # Rust 绿色版实现 (单 exe + pdfium.dll, 详见其 README)
```

仓库级文件（CHANGELOG / CONTRIBUTING / CI 配置等）见[仓库根目录](../../README.md)。


---

## 故障排查

### 双击 `.bat` 一闪而过

正常情况下脚本最后会等你按回车。如果一闪而过：

- 可能是 Python 没装或不在 PATH 里
- 在命令行手动跑 `python rename_invoice.py`（在本目录下）看具体报错

### `python` 命令不识别

```bash
'python' 不是内部或外部命令...
```

在 PATH 里加上 Python 目录：

1. `Win + R` → `sysdm.cpl` → 高级 → 环境变量
2. 用户变量 / 系统变量里的 `Path` → 编辑
3. 添加 Python 的安装目录（如 `C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python311\`）
4. 重新打开命令行

### 右键菜单没有出现

- Windows 11：点"显示更多选项"或按 `Shift + F10`
- 重新运行 `install_context.bat`
- 检查注册表 `HKEY_CURRENT_USER\Software\Classes\SystemFileAssociations\.pdf\shell\AddInvoicePrice` 是否存在

### 中文乱码

- 最新版本的 `.bat` 已经是 ASCII + CRLF，不应该有乱码
- 如果你修改过 `.bat`，注意：
  - 必须 CRLF 行尾（不是 LF）
  - 不要在 `rem` 注释里用中文（cmd 的 rem 解析对 UTF-8 不友好）
  - 如果非要写中文注释，用 `::` 代替 `rem`

### 提取到了错误的金额

理论上三层校验都通过的话，金额是对的。但万一：

1. 看 `rename_invoice.log` 找到对应记录
2. 在 PDF 阅读器里打开原始 PDF，对照"价税合计"
3. 如果确实错了，**告诉我具体的发票样本**，需要修改提取算法

### 想批量恢复（撤销）所有重命名

工具不带撤销功能（YAGNI），但日志够用：

```powershell
# 根据审计日志反向重命名（仅做演示，自己改路径）
Get-Content "<仓库>\apps\cli\rename_invoice.log" |
  Select-String "OK\s+(.+?\.pdf)\s+->\s+(.+?\.pdf)" |
  ForEach-Object { ... }
```

实际上手动改回也不慢，毕竟只是去掉前缀。


---

## 更新和卸载

### 更新依赖

```bash
pip install --upgrade pymupdf
```

### 完全卸载

1. 双击 `uninstall_context.bat`（清除右键菜单）
2. 删除整个仓库目录
3. （可选）`pip uninstall pymupdf`

被改名的 PDF 文件保留原状，不会被反向恢复。


---

## 常见问题

### Q：能处理扫描件（图片 PDF）吗？

不能。需要先用 OCR 工具把扫描件转成可搜索 PDF。设计上故意没集成 OCR，因为 OCR 识别错误会破坏可靠性保证。

### Q：能处理增值税普通发票吗？

可以。只要发票上有"价税合计（大写）"和 `¥XX.XX` 字段就能识别（增值税专票/普票/电子普票都符合）。

### Q：能处理多张 PDF 合并的文件吗？

每张发票独立校验。如果一个 PDF 里有多张发票，只能识别第一张匹配的。建议先拆分 PDF。

### Q：为什么不做 GUI？

CLI 本身 YAGNI——三种命令式入口已覆盖所有场景，可视反馈用安装时可选的"汇总窗口"（Tk 自带，零依赖）。
跨批次管理需求由仓库里的另一个程序 [account-manager](../account-manager/README.md) 承担；
Windows 11 新式右键菜单需求由 [explorer-extension](../explorer-extension/README.md) 承担。

### Q：右键之后什么都没发生，是不是工具坏了？

默认装的是**纯静默模式**，处理无窗口、无声音。验证方式：

1. 看文件名是否多了 `XX元-` 前缀
2. 打开本目录下的 `rename_invoice.log` 看最近的记录

如果都没有变化，重新双击 `install_context.bat`，第一问回 `y`（汇总窗口），下次右键就会弹窗告诉你结果。

### Q：怎么生成 Excel 汇总？

双击 `install_context.bat`，第二问回 `y`（"处理完后在文件夹生成 Excel 汇总?"）。之后每次右键，都会在被处理的文件夹下生成 `发票汇总_YYYYMMDD-HHMMSS.xlsx`。

列：发票文件名 / 发票号码 / 开票日期 / 销售方名称 / **备注名称（空，留你手填）** / **淘宝单号（空，留你手填）** / 金额。末行 `合计 = SUM(...)` 是公式不是死值，改任一行金额能自动重算。金额列是人民币货币格式（`¥X.XX`，负数红色）。

### Q：提取的精度是多少？

到分（0.01 元）。中文大写到 `分` 一级，比对容差 0.005 元，等同精确比对。

### Q：能改名规则吗（比如换成 `[98.01]文件名.pdf`）？

改 `rename_invoice.py` 第 ~190 行的：

```python
new_name = f'{amount_str}元-{name}'
```

改完顺便修改 `rename_invoice.py` 顶部的 `ALREADY_PREFIXED_RE` 正则，让"已加前缀"判断也跟着改，否则会重复加前缀。

### Q：怎么验证脚本本身没坏？

```bash
cd apps/cli
python test_parser.py
```

应该看到 `=== 15 passed, 0 failed ===`。


---

## 设计决策（给好奇的你）

- **为什么用 Python + PyMuPDF？** PyMuPDF 是开源 PDF 解析里中文支持最稳的，一次提取 + 自带文字层定位，不依赖外部 OCR。
- **为什么右键菜单走 pythonw.exe + 文件锁队列？** Windows 注册表 verb 模型每选一个文件就启一次进程；用 `pythonw.exe` 直接调可以零 cmd 窗口闪烁，并发的 N 个进程通过 `.queue.txt` + `msvcrt.locking` 选出一个 leader 统一处理 —— 避免 N 张发票产生 N 条日志批次或 N 个汇总窗口。
- **为什么销售方名称用坐标判断而不是文本顺序？** PyMuPDF 的文本提取顺序在不同发票布局里不一致（旧版"label 在前 / value 在后"和新版"label-value 同行"），但所有增值税发票都遵循"购方左 / 销方右"的版式约定。判断公司名块的水平中点 vs 页面中线是最稳的。
- **为什么用** `.bat` 而不是 `.ps1` 当主入口？ PowerShell 默认 ExecutionPolicy 限制要绕，`.bat` 双击直接跑。注册表的右键命令也一致用 `.bat`。
- **为什么用 HKCU 不用 HKLM？** 不需要管理员权限，不污染其他账户。代价是其他 Windows 账户登录看不到这个右键菜单——单用户机器无所谓。
- **为什么不做撤销？** 重命名是纯前缀添加，原始信息没丢失，手动改回比写撤销逻辑还快。带撤销反而引入复杂度和数据丢失风险。
- **为什么** `.ps1` 一定要 UTF-8 with BOM？ Windows PowerShell 5.1 读取无 BOM 文件时按系统 ANSI 代码页（中文版的 GBK）解释，会把 UTF-8 中文字节误读成乱码、甚至触发语法错误。PowerShell 7+ 没这问题，但 5.1 是 Win10/11 默认 PowerShell。


---
