# rename-invoice (Rust 单文件版)

发票 PDF 自动加价格前缀工具。**绿色版**：解压即用，不需要装 Python，不需要 pip install。

## 给小白用户的快速上手

1. 从 GitHub Releases 下载 `rename-invoice-windows-x64.zip`
2. 解压到任意文件夹（比如 `C:\Tools\rename-invoice\`）
3. 打开命令行 cd 到那个文件夹，跑一次：
   ```
   rename-invoice.exe install
   ```
   它会问两个 y/n 问题：
   - **是否处理完后弹出汇总窗口?** [y/N] —— 想看处理结果就回 y（Slint 原生窗口）
   - **是否处理完后在文件夹生成 Excel 汇总?** [y/N] —— 想要 Excel 就回 y

   然后右键菜单就装好了。
4. 在任意 PDF 文件 / 文件夹 / 文件夹空白处右键，会看到 **"添加发票价格前缀"**

完全不需要 Python、pip、命令行知识。

## 卸载

```
rename-invoice.exe uninstall
```

或者直接删掉文件夹（注册表里的右键菜单会变成"找不到目标"，需要再跑一次 uninstall 才完全干净）。

## 文件清单

解压后的 `rename-invoice-windows-x64/` 目录：

```
rename-invoice.exe        主程序 (console 子系统, 9.4 MB): install / uninstall / 直接模式 / 队列 worker
rename-invoice-w.exe      右键菜单前置 shim (windows 子系统, 0.25 MB): 0 cmd 闪窗, 见下节
pdfium.dll                Google PDFium PDF 解析库 (Apache-2.0)
PDFIUM_LICENSE            PDFium 许可证 (再分发要求)
icon.ico                  右键菜单图标 (可选, 见下)
README.md                 本说明
```

**两个 `.exe` 加上 `pdfium.dll` 必须在同一目录**。`install` 子命令会把右键菜单注册到 `rename-invoice-w.exe`。

`icon.ico` 在同目录时，右键菜单的图标指向它；不在就回退到 `.exe` 内嵌的图标资源。之所以优先 `.ico`：Explorer 每次构建右键菜单都要打开图标源文件抽资源，指向 ~10 MB 的 `.exe` 会让菜单弹出明显变慢，指向几 KB 的 `.ico` 就没这个开销。

## 多选 N 个 PDF 时到底发生了什么

Windows 的 legacy verb（`shell\<Verb>\command` + `%1`）是"一个文件一个进程"的模型：**选中 23 个 PDF，Explorer 就 CreateProcess 23 次**，每次只塞一个路径进去。这个行为改不了（除非改写成 COM DropTarget）。能改的只有"每个进程有多重"，所以两个 .exe 是这样分工的：

```
Explorer ──启动 N 次──▶ rename-invoice-w.exe   0.25 MB, windows 子系统
                          ├─ 过闸门 (同时干活的最多 12 个)
                          ├─ 把自己那条路径 append 进 .queue.txt
                          ├─ 抢 .spawn.lock (try_lock, 抢不到就直接退)
                          └─ 抢到且没有 worker ─┐  只有 1 个 shim 会走到这
                                                ▼
                        rename-invoice.exe --silent --from-queue
                          9.4 MB, 全程只有 1 个
                          排空队列 → 处理全部 PDF → xlsx / 汇总窗口
```

要点：

- **重进程恒为 1 个。** worker 排空队列后不会立刻退，会再空转 800 ms（`silent.rs` 的 `LINGER`），把 Explorer 陆续启动的整个波次吃完。不然尾巴上的 shim 发现没 worker 又会拉起一个。
- **先入队、再判断。** 顺序反过来的话，worker 刚好在这两步之间退出，那条路径就没人处理了。
- **闸门 `RENAME_INVOICE_MAX_PROCS`（默认 12）** 是个命名信号量，限制同时在干活的 shim 数量。被挡住的 shim 是在信号量上短暂等待，不是被丢弃，所以一个文件都不会丢；也因为是"等待"，任务管理器里瞬时看到的进程数可能略高于 12。默认取 12 是按普通办公机（4~8 核）来的，再多只会让文件锁争抢和杀软扫描互相拖慢。
- 注册表 verb 上写了 `MultiSelectModel=Player`，把 legacy verb 的多选上限从默认的 15 抬到 100。超过 100 个 Explorer 会直接不显示菜单项，那种情况直接右键所在文件夹（worker 会扫掉整个目录）。

实测（100 个 PDF 全选、快速并发启动）：重进程 1 个、轻进程活跃峰值 3 个、总耗时 3.1 s、100/100 全部处理、队列无残留。

## 给开发者

```bash
cd rust
# 拉一份 pdfium.dll 到本地 (Win x64)
.\scripts\fetch_pdfium.ps1

# 单元测试
cargo test --bin rename-invoice

# Release 编译
cargo build --release

# 打包发布:
# 把以下文件压成 zip 上传 GH release:
#   target/release/rename-invoice.exe
#   target/release/rename-invoice-w.exe
#   pdfium.dll
#   PDFIUM_LICENSE
#   assets/icon.ico   -> 压包时放到根目录, 命名为 icon.ico (install 会优先用它当菜单图标)
#   README.md
```

## 命令行参数

```
rename-invoice.exe [paths...]                 直接模式 (cmd 输出彩色结果)
rename-invoice.exe --silent [paths...]        静默 + 队列锁 (右键菜单走这条)
rename-invoice.exe --silent --xlsx [paths]    + 生成 Excel 汇总
rename-invoice.exe --silent --summary [path]  + 弹 Slint 汇总窗口
rename-invoice.exe --silent --from-queue      路径全部来自 .queue.txt (shim 拉起 worker 时用)
rename-invoice.exe install [--summary] [--xlsx]   注册右键菜单 (HKCU)
rename-invoice.exe uninstall                  卸载右键菜单
```

无参数时扫描当前工作目录（拖放/双击场景）。

## Rust 版与 Python 版的对应关系

| 能力 | Python v0.4.0 | Rust v0.5.0 |
|------|---------------|-------------|
| 三层金额校验 | ✅ | ✅ |
| 重命名为 `XX元-原名` | ✅ | ✅ |
| 静默模式 + 文件锁 leader | ✅ (msvcrt) | ✅ (fs2) |
| Excel 汇总 + 货币格式 + SUM 公式 | ✅ (openpyxl) | ✅ (rust_xlsxwriter) |
| 销售方坐标判断 | ✅ (PyMuPDF) | ✅ (PDFium) |
| 安装两问交互 | ✅ (install_context.bat) | ✅ (`install` 子命令) |
| 汇总窗口 | ✅ (tkinter) | ✅ (Slint 原生窗口) |
| 部署 | 装 Python + pip install | 解压 zip 即用 |

## 用了哪些 crate

- `pdfium-render` — 调 Google PDFium 解析 PDF (动态加载 pdfium.dll)
- `rust_xlsxwriter` — 写 Excel
- `slint` — 汇总窗口 GUI (`--summary` 用)
- `regex` — 正则
- `chrono` — 时间戳
- `fs2` — 文件锁
- `winreg` — 注册表
- `windows-sys` — Win32 API
- `winresource` (build) — .exe 嵌入 icon resource
- `anyhow` — 错误处理

Cargo.toml 里 `[profile.release]` 开了 `lto + strip + opt-level=3`。`rename-invoice.exe` 约 9.4 MB（Slint UI 引擎占大头）；`rename-invoice-w.exe` 只用 std + fs2 + windows-sys，约 0.25 MB。
