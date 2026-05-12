"""Windows-only: ShowWindow-based hide/restore for the Flet main window.

Why this exists
---------------
Flet 0.85's Window class has no explicit show/restore/hide methods --
only `destroy`, `close`, `center`, `to_front`. Hiding is supposed to
go through the `minimized` + `skip_task_bar` properties, batched via
`page.window.update()`.

In practice on Windows 11 + Flet 0.85, the round-trip is broken:
setting `minimized = True` + `skip_task_bar = True` hides the window
fine, but setting them back to False leaves the window stuck minimized
with no taskbar entry -- unreachable for the user. Splitting into two
update() calls didn't help.

Win32's `ShowWindow(hwnd, SW_HIDE/SW_RESTORE)` is the standard
mechanism every tray app uses. We bypass Flet entirely for this one
state transition; everything else (size, position, theme, controls)
still flows through Flet normally.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Optional

# ShowWindow nCmdShow values
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

_hwnd_cache: Optional[int] = None


if sys.platform == "win32":
    _user32 = ctypes.windll.user32

    _FindWindowW = _user32.FindWindowW
    _FindWindowW.restype = wintypes.HWND
    _FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]

    _ShowWindow = _user32.ShowWindow
    _ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _ShowWindow.restype = wintypes.BOOL

    _SetForegroundWindow = _user32.SetForegroundWindow
    _SetForegroundWindow.argtypes = [wintypes.HWND]
    _SetForegroundWindow.restype = wintypes.BOOL

    _IsWindow = _user32.IsWindow
    _IsWindow.argtypes = [wintypes.HWND]
    _IsWindow.restype = wintypes.BOOL


def _find_hwnd(title: str) -> Optional[int]:
    """Look up our top-level window's HWND by title (cached after first hit).

    The Flet runtime creates exactly one main window per process with the
    title we passed via `page.title`. FindWindowW is sufficient.
    """
    global _hwnd_cache
    if sys.platform != "win32":
        return None
    if _hwnd_cache and _IsWindow(_hwnd_cache):
        return _hwnd_cache
    hwnd = _FindWindowW(None, title)
    if hwnd:
        _hwnd_cache = hwnd
        return hwnd
    return None


def hide(title: str) -> bool:
    """ShowWindow(SW_HIDE). Returns True iff the hwnd was located and hidden."""
    hwnd = _find_hwnd(title)
    if not hwnd:
        return False
    _ShowWindow(hwnd, SW_HIDE)
    return True


def restore(title: str) -> bool:
    """ShowWindow(SW_RESTORE) + SetForegroundWindow.

    Works regardless of current window state (hidden / minimized / normal).
    Returns True iff the hwnd was located.
    """
    hwnd = _find_hwnd(title)
    if not hwnd:
        return False
    _ShowWindow(hwnd, SW_RESTORE)
    _SetForegroundWindow(hwnd)
    return True
