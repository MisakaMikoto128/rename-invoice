# BUILD — Account Manager Windows EXE

How to produce a stand-alone Windows executable for the account-manager Flet GUI.
End users get a single `.exe` they double-click; no Python install required.

## Prerequisites

Already installed in the dev environment:

- Python 3.11 (CPython, x64)
- `flet==0.85.0` (`pip show flet`)
- `pyinstaller>=6.13` (`pip show pyinstaller`)
- Runtime deps from `requirements.txt` (`pymupdf`, `openpyxl`, `flet`)

If `pyinstaller` is missing, install it: `pip install pyinstaller`.

## Flet 0.85 packaging options (for context)

`flet --help` lists two relevant subcommands:

| Command | What it does | Needs |
|---|---|---|
| `flet pack` | Wraps PyInstaller, adds Flet-specific runtime hooks (Flutter view, icon update). | PyInstaller only. |
| `flet build windows` | Newer Flutter-based packager. Produces a smaller MSIX-style bundle. | Flutter SDK installed locally (we don't have it). |

We use **`flet pack`** — it is the simpler PyInstaller wrapper and works with the
toolchain already on this machine.

## Build command

Run from repo root (`C:\Users\liuyu\tools\rename_invoice`):

```powershell
flet pack accounting/ui/app.py `
  --name AccountManager `
  --icon assets/icon.ico `
  --add-data "rename_invoice.py;." `
  --hidden-import rename_invoice fitz openpyxl `
  --product-name "AccountManager" `
  --file-description "Account Manager for rename-invoice" `
  -y `
  "--pyinstaller-build-args=--exclude-module=matplotlib" `
  "--pyinstaller-build-args=--exclude-module=PyQt5" `
  "--pyinstaller-build-args=--exclude-module=PyQt6" `
  "--pyinstaller-build-args=--exclude-module=PySide2" `
  "--pyinstaller-build-args=--exclude-module=PySide6" `
  "--pyinstaller-build-args=--exclude-module=scipy" `
  "--pyinstaller-build-args=--exclude-module=pandas" `
  "--pyinstaller-build-args=--exclude-module=tables" `
  "--pyinstaller-build-args=--exclude-module=IPython" `
  "--pyinstaller-build-args=--exclude-module=notebook" `
  "--pyinstaller-build-args=--exclude-module=jupyter" `
  "--pyinstaller-build-args=--exclude-module=sphinx" `
  "--pyinstaller-build-args=--exclude-module=pytest"
```

Notes on the flags:

- `--add-data "rename_invoice.py;."` bundles `rename_invoice.py` (top-level
  script at repo root) into the exe payload. The semicolon `;` is the Windows
  PyInstaller separator (Linux/macOS uses `:`).
- `--hidden-import rename_invoice fitz openpyxl` — PyInstaller sees these via
  static analysis but the script-not-package layout sometimes confuses it;
  belt-and-braces. (`flet pack`'s `--hidden-import` accepts multiple values.)
- `accounting/extractor.py` was patched to look for `rename_invoice.py` in
  `sys._MEIPASS` when `sys.frozen` is set. Without that, the bundled copy is
  not found at runtime.
- `--pyinstaller-build-args=--exclude-module=X` — `flet pack` does not expose
  PyInstaller's `--exclude-module` directly, so we pass it through. The
  `--pyinstaller-build-args=...` form (single token, `=`, quoted) is required
  because argparse with `nargs='*'` will reject following `--`-prefixed
  tokens; one repeated `--pyinstaller-build-args=...` per exclude works.
- The 13 `--exclude-module` flags strip dev-only packages (matplotlib, PyQt,
  scipy, pandas, jupyter stack, etc.) that PyInstaller pulls in transitively
  from the dev environment. None of these are runtime deps — see
  `requirements.txt`. **Do not** exclude `numpy` or `lxml` blindly: openpyxl /
  pymupdf reach for them in some code paths.

## Output

```
dist/AccountManager.exe   (~ 106 MB, single-file)
build/AccountManager/...  (PyInstaller intermediates — gitignored)
AccountManager.spec       (PyInstaller spec — gitignored)
```

Both `build/`, `dist/`, and `*.spec` are listed in `.gitignore`. **Do not
commit the binary** — it ships via GitHub Releases.

Without the `--exclude-module` flags the exe was ~237 MB, dominated by
transitive deps PyInstaller picks up from the dev site-packages (matplotlib,
PyQt5, scipy, pandas, jupyter, …). With the excludes above the exe drops to
~106 MB and still passes the 12-second smoke test below.

## Smoke test

```powershell
$p = Start-Process -FilePath ".\dist\AccountManager.exe" -PassThru
Start-Sleep -Seconds 12
$alive = !$p.HasExited
if ($alive) { Stop-Process -Id $p.Id -Force }
Write-Host "Exe alive after 12s: $alive"
```

A onefile PyInstaller exe needs ~5-8 s to unpack into `%TEMP%\_MEIxxxxx`, then
Flet spins up the Flutter view. If `$alive` is `True` after 12 s, the bundle
loaded cleanly.

## Caveats

- **Antivirus**. A freshly-built PyInstaller bootloader is sometimes flagged
  by Windows Defender / SmartScreen. Code-signing the exe before a Release
  upload would fix this; we have no cert yet.
- **First launch is slow.** Onefile mode unpacks ~250 MB to `%TEMP%` on every
  cold start. If we care, switch to `flet pack -D ...` (one-folder mode) — the
  user gets a folder with `AccountManager.exe` inside, which starts in <1 s
  but distributes as a zip rather than a single file.
- **Excluded heavy deps.** The 13 `--exclude-module` flags above already
  trim the exe from 237 MB to ~106 MB. Pushing further (excluding `numpy`,
  `lxml`, `cryptography`, `tkinter`) is risky — at least one of openpyxl /
  pymupdf / Flet's runtime imports them. Test before adding more.
- **Dev path unchanged.** `python -m accounting.ui.app` still works for
  development; the frozen-vs-source path branch in `accounting/extractor.py`
  picks the right `_REPO_ROOT` automatically.
