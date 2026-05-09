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
rename-invoice.exe        主程序 (图标已嵌入)
pdfium.dll                Google PDFium PDF 解析库 (Apache-2.0)
PDFIUM_LICENSE            PDFium 许可证 (再分发要求)
README.md                 本说明
```

**`pdfium.dll` 必须和 `rename-invoice.exe` 在同一目录**，否则程序会报"找不到 pdfium.dll"。

`.exe` 自带程序图标和右键菜单图标（Windows ICON RESOURCE），不需要额外文件。

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
#   pdfium.dll
#   PDFIUM_LICENSE
#   assets/icon.ico
#   README.md
```

## 命令行参数

```
rename-invoice.exe [paths...]                 直接模式 (cmd 输出彩色结果)
rename-invoice.exe --silent [paths...]        静默 + 队列锁 (右键菜单走这条)
rename-invoice.exe --silent --xlsx [paths]    + 生成 Excel 汇总
rename-invoice.exe --silent --summary [path]  + 弹 Tk 汇总窗口 (TODO 后续版本)
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

Cargo.toml 里 `[profile.release]` 开了 `lto + strip + opt-level=3`, 单 .exe 约 10 MB (Slint UI 引擎占大头).
