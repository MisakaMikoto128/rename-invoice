# BUILD — Account Manager Windows EXE

How to produce a stand-alone Windows executable for the account-manager Flet GUI.
End users get a single `.exe` they double-click; no Python install required.

**Packager: PyInstaller** (via `flet pack`). Single command:

```powershell
.\build.bat
# or:
python build.py
```

Output: `release\v<version>\AccountManager.exe` (~80 MB, single-file).

## Prerequisites

Already installed in the dev environment:

- Python 3.11 (CPython, x64)
- `flet==0.85.0` (`pip show flet`)
- `pyinstaller>=6.13` (`pip install pyinstaller`)
- Runtime deps from `requirements.txt` (`pymupdf`, `openpyxl`, `flet`)

## What `build.py` does

1. Detects the version from `git describe --tags --abbrev=0` (fallback: `0.0.<YYYYMMDD>`).
2. Wipes stale `dist/`, `build/`, `*.spec`.
3. Runs `flet pack accounting/ui/app.py` with:
   - `--name AccountManager` / `--icon assets/icon.ico`
   - `--add-data "rename_invoice.py;."` — bundles the CLI module
   - `--hidden-import rename_invoice fitz openpyxl`
   - 29 `--pyinstaller-build-args=--exclude-module=...` flags trimming the bundle from ~242 MB to ~80 MB
4. Copies `dist\AccountManager.exe` → `release\v<version>\AccountManager.exe`.
5. (Optional) self-signs via `signtool` if it's on PATH or the Win 10 SDK is installed; auto-generates a self-signed cert (`build_sign.pfx`) on first run.

`build.bat` is a thin wrapper over `python build.py` for double-click convenience.

## Excludes — what we strip and why

| Group | Modules | Reason |
|---|---|---|
| GUI toolkits we don't ship | `PyQt5/6`, `PySide2/6`, `tkinter` | Flet uses Flutter, not Qt/Tk. |
| Plotting / sci stack | `matplotlib`, `scipy`, `pandas`, `numpy`, `tables` | Not used. PyInstaller pulls them transitively from a dev box. |
| Notebook stack | `IPython`, `jupyter`, `notebook`, `ipywidgets`, `ipykernel`, `jupyter_client`, `zmq`, `debugpy`, `tornado` | Dev tooling only. |
| XML / TLS | `lxml`, `cryptography` | openpyxl works with stdlib `xml.etree`; no TLS at runtime (offline app). |
| Test / docs | `pytest`, `_pytest`, `sphinx`, `pygments` | Test/build-time only. |
| Build tooling | `pip`, `distutils`, `dill`, `fontTools` | Not needed at runtime. |

`setuptools` and `wheel` are intentionally **not** excluded — PyInstaller's `pyi_rth_pkgres` runtime hook imports `pkg_resources` (provided by setuptools) at startup, and excluding `wheel` makes the build itself fail with `ValueError: Target module "wheel" already imported as "ExcludedModule"`.

If we ever start generating xlsx with charts, embedded images, or pivot tables, re-test the `numpy` / `lxml` excludes — openpyxl's optional code paths reach for them.

## Smoke test

```powershell
$exe = Get-ChildItem release\v*\AccountManager.exe | Select-Object -First 1 -ExpandProperty FullName
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 15
$alive = !$p.HasExited
if ($alive) { Stop-Process -Id $p.Id -Force }
Write-Host "Exe alive after 15s: $alive"
```

A onefile PyInstaller exe needs ~5-8 s to unpack into `%TEMP%\_MEIxxxxx`, then Flet spins up the Flutter view. If `$alive` is `True` after 15 s, the bundle loaded cleanly.

**Caveat.** Don't pass `-RedirectStandardOutput` / `-RedirectStandardError` to `Start-Process` — PyInstaller built the bundle with `--noconsole`, so the parent process re-execs into a windowed Flet child and the redirected-stdio parent exits within seconds, making `$alive` look `False` even when the GUI is fine.

### Tray / autostart / close-confirm smoke checklist

Run after each new build (v1.0.2+):

1. 双击 exe → 主窗出现 + 托盘有图标 ✓
2. 点 ─ → 主窗消失,任务栏按钮消失,托盘仍在 ✓
3. 左键托盘图标 → 主窗弹回 ✓
4. 点 ✕ → 弹「关闭确认」对话框 ✓
5. 选「隐藏到托盘」+ 不勾「记住」→ 隐藏;下次再点 ✕ 还弹 ✓
6. 选「退出」+ 勾「记住」→ 进程退出;重启 exe 后再点 ✕ 直接退出 ✓
7. 设置 → 关闭时改回「询问」→ 下次点 ✕ 又弹对话框 ✓
8. 设置 → 开机启动 ON → 任务管理器「启动应用」可见 AccountManager ✓
9. 已在托盘运行时双击 exe → 主窗弹出,无第二个进程
   验证: `Get-Process AccountManager` 只一个 ✓
10. 设置 → 开机启动 OFF → 任务管理器「启动应用」AccountManager 消失 ✓

## Known caveats

- **Antivirus.** A freshly-built PyInstaller bootloader is sometimes flagged by Windows Defender / SmartScreen. Code-signing fixes this; we use a self-signed cert which helps with SmartScreen but doesn't beat AV reputation. A real Authenticode cert would be the eventual fix.
- **Cold start.** Onefile mode unpacks ~250 MB to `%TEMP%` on every launch — first run is ~5-8 s. If we care, switch to `flet pack -D ...` (one-folder mode) — boots in <1 s but distributes as a zip.
- **Dev path unchanged.** `python -m accounting.ui.app` still works for development; the frozen-vs-source path branch in `accounting/extractor.py` picks the right `_REPO_ROOT` automatically.

## Why not Nuitka

For v1.0.1 (smaller-exe goal) we tried Nuitka 2.6.8 (`build.py` was originally a Nuitka wrapper). Two attempts both hung on PyMuPDF's SWIG-generated `pymupdf.mupdf` module — Nuitka's optimiser entered an unbounded `loop_analysis` / `new_builtin` rewrite cycle. Even after dropping `--lto=yes`, dropping all `--include-package=` flags, and adding `--show-progress` for visibility, the import-analysis phase stalled past 2 hours with the err log frozen.

PyInstaller with the exclude list above:

| | PyInstaller | Nuitka (attempted) |
|---|---|---|
| Build time | ~30 s | 2+ hr (hung) |
| Final size | ~80 MB | unknown — never finished |
| Reverse-engineering | Easy (.pyc) | Harder (compiled) |
| AV false positives | Sometimes | Rare |

The size advantage Nuitka *might* have offered is small enough that the build-time cost (and the SWIG-bindings landmine for any future PyMuPDF upgrade) isn't worth it.
