#!/usr/bin/env python3
"""
Account Manager - Windows EXE build (PyInstaller via `flet pack`)

Usage:
    python build.py        # or: .\\build.bat

Output:
    release/v<version>/AccountManager.exe   (~75 MB, single-file)

Prereqs (one-time):
    pip install -r requirements.txt
    pip install pyinstaller

Why PyInstaller over Nuitka:
    Tried Nuitka 2.6.8 for v1.0.1 (smaller-exe goal). It hung in import
    analysis on PyMuPDF's SWIG-generated bindings (`pymupdf.mupdf`) for
    hours, even with module-include flags trimmed and `--lto=yes` dropped.
    PyInstaller with the exclude list below builds in ~30 s and produces
    a 75 MB exe -- close enough to Nuitka's projected size that the
    build-time cost isn't worth it.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
ENTRY      = SCRIPT_DIR / "accounting" / "ui" / "app.py"
ICON       = SCRIPT_DIR / "assets" / "icon.ico"
RENAME_PY  = SCRIPT_DIR.parent / "cli" / "rename_invoice.py"
DIST_EXE   = SCRIPT_DIR / "dist" / "AccountManager.exe"
RELEASE    = SCRIPT_DIR / "release"

APP_NAME = "AccountManager"
APP_DESC = "Account Manager - rename-invoice GUI"

# ~80 MB after these 29 excludes; without them the bundle is ~242 MB.
# Each entry is a top-level package PyInstaller would otherwise pull in
# transitively from the dev site-packages but our app never imports.
# v1.0.0 baseline (13) + v1.0.1 additions (15). All proven safe by smoke
# tests in BUILD.md. setuptools / wheel intentionally NOT excluded -
# PyInstaller's pyi_rth_pkgres hook needs them at runtime.
EXCLUDES = [
    "matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6",
    "scipy", "pandas", "tables",
    "IPython", "notebook", "jupyter", "jupyter_client",
    "ipywidgets", "ipykernel",
    "sphinx", "pytest", "_pytest", "pip", "distutils",
    "tkinter", "numpy", "lxml", "cryptography", "pygments",
    "zmq", "debugpy", "tornado", "dill", "fontTools",
]

CERT_PFX = SCRIPT_DIR / ".sign" / "build_sign.pfx"
CERT_PWD = "AcctMgr_Build_Sign!"


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def get_version() -> str:
    try:
        r = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=SCRIPT_DIR,
        )
        if r.returncode == 0:
            return r.stdout.strip().lstrip("v")
    except FileNotFoundError:
        pass
    return f"0.0.{datetime.now().strftime('%Y%m%d')}"


# -- Code signing (optional) ----------------------------------

def _find_signtool() -> Path | None:
    p = shutil.which("signtool")
    if p:
        return Path(p)
    kits = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if not kits.exists():
        return None
    for cand in sorted(kits.glob("*/x64/signtool.exe"), reverse=True):
        return cand
    return None


def _ensure_cert() -> bool:
    if CERT_PFX.exists():
        return True
    log("Creating self-signed code-signing cert (one-time)...")
    ps = (
        f"$pwd = ConvertTo-SecureString -String '{CERT_PWD}' -Force -AsPlainText; "
        f"$cert = New-SelfSignedCertificate -Type CodeSigning "
        f"-Subject 'CN=rename-invoice' -CertStoreLocation 'Cert:\\CurrentUser\\My' "
        f"-NotAfter (Get-Date).AddYears(5) -HashAlgorithm SHA256; "
        f"Export-PfxCertificate -Cert $cert -FilePath '{CERT_PFX}' -Password $pwd | Out-Null"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True, text=True, timeout=30,
    )
    return r.returncode == 0 and CERT_PFX.exists()


def sign_exe(exe: Path) -> None:
    tool = _find_signtool()
    if not tool:
        log("signtool not found; skipping code-sign.")
        return
    if not _ensure_cert():
        log("cert creation failed; skipping code-sign.")
        return
    base = [str(tool), "sign", "/f", str(CERT_PFX), "/p", CERT_PWD,
            "/fd", "SHA256", "/d", APP_DESC]
    for ts in ("http://timestamp.digicert.com", "http://timestamp.sectigo.com"):
        r = subprocess.run(base + ["/tr", ts, "/td", "SHA256", str(exe)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            log(f"Signed (timestamp {ts}).")
            return
    r = subprocess.run(base + [str(exe)], capture_output=True, text=True)
    log("Signed (no timestamp)." if r.returncode == 0 else "Sign failed.")


# -- Build ----------------------------------------------------

def build() -> None:
    version = get_version()
    log(f"version = {version}")

    for d in ("dist", "build"):
        p = SCRIPT_DIR / d
        if p.exists():
            shutil.rmtree(p)
    for spec in SCRIPT_DIR.glob("*.spec"):
        spec.unlink()

    flet_cli = shutil.which("flet")
    if not flet_cli:
        sys.exit("[build] `flet` CLI not on PATH (pip install flet)")

    cmd: list[str] = [
        flet_cli, "pack", str(ENTRY),
        "--name", APP_NAME,
        "--icon", str(ICON),
        "--add-data", f"{RENAME_PY};.",
        "--hidden-import", "rename_invoice",
        "--hidden-import", "fitz",
        "--hidden-import", "openpyxl",
        "--product-name", APP_NAME,
        "--file-description", APP_DESC,
        "-y",
    ]
    cmd += [f"--pyinstaller-build-args=--exclude-module={m}" for m in EXCLUDES]

    log(f"running flet pack ({len(EXCLUDES)} excludes)...")
    r = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if r.returncode != 0:
        sys.exit(f"[build] flet pack failed (exit {r.returncode})")

    if not DIST_EXE.exists():
        sys.exit(f"[build] expected output missing: {DIST_EXE}")

    out_dir = RELEASE / f"v{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_exe = out_dir / DIST_EXE.name
    if out_exe.exists():
        out_exe.unlink()
    shutil.copy2(DIST_EXE, out_exe)
    size_mb = out_exe.stat().st_size / 1_048_576
    log(f"output -> {out_exe}  ({size_mb:.1f} MB)")

    sign_exe(out_exe)
    log("done.")


if __name__ == "__main__":
    build()
