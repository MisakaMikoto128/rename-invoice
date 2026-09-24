"""Windows-only: manage HKCU\\...\\Run autostart entry for AccountManager."""
from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AccountManager"


def is_enabled() -> bool:
    """Return True iff the Run-key entry exists for our app."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable(exe_path: Path) -> None:
    """Write the Run-key entry. Value = quoted exe path.

    Raises OSError on permission failure (caller surfaces a UI error).
    Refuses to write if exe_path doesn't point to an .exe (dev mode would
    otherwise write the python interpreter path).
    """
    if winreg is None:
        raise OSError("autostart is only supported on Windows")
    if exe_path.suffix.lower() != ".exe" or "python" in exe_path.name.lower():
        raise OSError("开机启动仅在打包版 AccountManager.exe 中可用")
    value = f'"{exe_path}"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)


def disable() -> None:
    """Remove the Run-key entry. No-op if it doesn't exist."""
    if winreg is None:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        return


def current_exe_path() -> Path:
    """Return absolute path to the running exe (PyInstaller bundle aware).

    In dev mode (running from source) this returns the python interpreter,
    which is not what we want — caller should guard with `getattr(sys, 'frozen', False)`.
    """
    return Path(sys.executable).resolve()
