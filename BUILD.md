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
  --hidden-import rename_invoice `
  --hidden-import fitz `
  --hidden-import openpyxl `
  --product-name "AccountManager" `
  --file-description "Account Manager for rename-invoice" `
  -y
```

Notes on the flags:

- `--add-data "rename_invoice.py;."` bundles `rename_invoice.py` (top-level
  script at repo root) into the exe payload. The semicolon `;` is the Windows
  PyInstaller separator (Linux/macOS uses `:`).
- `--hidden-import rename_invoice` — PyInstaller sees the import via static
  analysis but the script-not-package layout sometimes confuses it; this is
  belt-and-braces.
- `--hidden-import fitz` / `--hidden-import openpyxl` — same reason, both are
  imported lazily inside `rename_invoice.py`.
- `accounting/extractor.py` was patched to look for `rename_invoice.py` in
  `sys._MEIPASS` when `sys.frozen` is set. Without that, the bundled copy is
  not found at runtime.

## Output

```
dist/AccountManager.exe   (~ 237 MB, single-file)
build/AccountManager/...  (PyInstaller intermediates — gitignored)
AccountManager.spec       (PyInstaller spec — gitignored)
```

Both `build/`, `dist/`, and `*.spec` are listed in `.gitignore`. **Do not
commit the binary** — it ships via GitHub Releases.

The size (~237 MB) is dominated by transitive deps PyInstaller picks up from
the dev site-packages (matplotlib, PyQt5, numpy, scipy, pandas). A future
optimisation is to add `--exclude-module matplotlib --exclude-module PyQt5
--exclude-module scipy --exclude-module pandas` etc. — none of those are
needed at runtime.

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
- **Excluded heavy deps.** See "Output" above. Trimming would shrink the exe
  to <100 MB.
- **Dev path unchanged.** `python -m accounting.ui.app` still works for
  development; the frozen-vs-source path branch in `accounting/extractor.py`
  picks the right `_REPO_ROOT` automatically.
