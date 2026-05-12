"""Windows-only: ShowWindow-based hide/restore for the Flet main window.

Why this exists
---------------
Flet 0.85's Window class has no explicit show/restore/hide methods --
only `destroy`, `close`, `center`, `to_front`. Hiding is supposed to
go through `minimized` + `skip_task_bar` properties via
`page.window.update()`. On Windows 11 + Flet 0.85, the round-trip is
broken: hide works, but the window then stays stuck minimized with no
taskbar entry, unreachable. Bypass Flet for this state transition.

Finding the right HWND
----------------------
Flet 0.85 spawns a child `flet.exe` process that owns the actual OS
window. `os.getpid()` is the PYTHON pid; enumerating windows by that
PID returns nothing. The Flutter window lives in a descendant
process and has class name `FLUTTER_RUNNER_WIN32_WINDOW`.

Strategy:
1. Use kernel32 Tool-Help to walk the process tree, collecting our
   descendants (children, grandchildren, ...).
2. Enumerate top-level windows; pick the one with class
   `FLUTTER_RUNNER_WIN32_WINDOW` whose pid is in our descendant set.
3. Cache the HWND between calls; revalidate via IsWindow.
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
from ctypes import wintypes
from typing import Optional, Set

log = logging.getLogger(__name__)

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

FLUTTER_CLS = "FLUTTER_RUNNER_WIN32_WINDOW"

_hwnd_cache: Optional[int] = None


if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    _EnumWindows = _user32.EnumWindows
    _EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
    _EnumWindows.restype = wintypes.BOOL

    _GetWindowThreadProcessId = _user32.GetWindowThreadProcessId
    _GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _GetWindowThreadProcessId.restype = wintypes.DWORD

    _GetClassNameW = _user32.GetClassNameW
    _GetClassNameW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _GetClassNameW.restype = ctypes.c_int

    _ShowWindow = _user32.ShowWindow
    _ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _ShowWindow.restype = wintypes.BOOL

    _SetForegroundWindow = _user32.SetForegroundWindow
    _SetForegroundWindow.argtypes = [wintypes.HWND]
    _SetForegroundWindow.restype = wintypes.BOOL

    _IsWindow = _user32.IsWindow
    _IsWindow.argtypes = [wintypes.HWND]
    _IsWindow.restype = wintypes.BOOL

    # --- Tool-Help (process tree) ---
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    _CreateToolhelp32Snapshot = _kernel32.CreateToolhelp32Snapshot
    _CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    _Process32FirstW = _kernel32.Process32FirstW
    _Process32FirstW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32FirstW.restype = wintypes.BOOL

    _Process32NextW = _kernel32.Process32NextW
    _Process32NextW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32NextW.restype = wintypes.BOOL

    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL


def _descendant_pids(root_pid: int) -> Set[int]:
    """Return all PIDs that descend from root_pid (children, grandchildren, ...)."""
    if sys.platform != "win32":
        return set()
    snap = _CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == 0 or snap == INVALID_HANDLE_VALUE:
        return set()
    entries: list[tuple[int, int]] = []  # (pid, parent_pid)
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        if _Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                entries.append((pe.th32ProcessID, pe.th32ParentProcessID))
                if not _Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        _CloseHandle(snap)

    # BFS from root_pid
    children_map: dict[int, list[int]] = {}
    for pid, ppid in entries:
        children_map.setdefault(ppid, []).append(pid)

    out: Set[int] = set()
    stack = [root_pid]
    while stack:
        cur = stack.pop()
        for child in children_map.get(cur, []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def _debug_log(msg: str) -> None:
    """Write a line to %TEMP%/rename_invoice_win32.log for ad-hoc debugging."""
    try:
        path = os.path.join(os.environ.get("TEMP", "."),
                            "rename_invoice_win32.log")
        with open(path, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def _find_hwnd() -> Optional[int]:
    """Find the Flutter main window HWND for our app (cached)."""
    global _hwnd_cache
    if sys.platform != "win32":
        return None
    if _hwnd_cache and _IsWindow(_hwnd_cache):
        _debug_log(f"_find_hwnd: cache hit 0x{_hwnd_cache:X}")
        return _hwnd_cache

    descendants = _descendant_pids(os.getpid())
    _debug_log(f"_find_hwnd: my_pid={os.getpid()} descendants={descendants}")
    if not descendants:
        log.warning("_win32_window: no descendant processes found")
        return None

    # Collect every Flutter window we can see across all PIDs for diagnostics,
    # then filter down to the descendants set.
    all_flutter: list[tuple[int, int]] = []      # (hwnd, pid) for any FLUTTER cls
    descendant_flutter: list[int] = []           # hwnds that match descendants

    @_EnumWindowsProc
    def cb(hwnd, _l):
        try:
            pid = wintypes.DWORD()
            _GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            cls_buf = ctypes.create_unicode_buffer(256)
            _GetClassNameW(hwnd, cls_buf, 256)
            if cls_buf.value == FLUTTER_CLS:
                all_flutter.append((hwnd, pid.value))
                if pid.value in descendants:
                    descendant_flutter.append(hwnd)
        except Exception:
            pass
        return True

    _EnumWindows(cb, 0)
    _debug_log(f"_find_hwnd: all_flutter_windows={all_flutter} "
               f"descendant_matches={descendant_flutter}")

    if descendant_flutter:
        _hwnd_cache = descendant_flutter[0]
        _debug_log(f"_find_hwnd: SUCCESS cached hwnd=0x{_hwnd_cache:X}")
        return _hwnd_cache

    # Fallback: if there's exactly one Flutter window system-wide and no
    # descendant match, assume it's ours (Flet's subprocess hierarchy on
    # some setups may not be reachable from our pid).
    if len(all_flutter) == 1:
        _hwnd_cache = all_flutter[0][0]
        _debug_log(f"_find_hwnd: FALLBACK using lone Flutter window "
                   f"hwnd=0x{_hwnd_cache:X} pid={all_flutter[0][1]}")
        return _hwnd_cache

    _debug_log(f"_find_hwnd: FAILED — {len(all_flutter)} Flutter windows but "
               f"none in descendants {descendants}")
    return None


def hide() -> bool:
    """ShowWindow(SW_HIDE). True iff hwnd was located."""
    hwnd = _find_hwnd()
    if not hwnd:
        _debug_log("hide(): _find_hwnd returned None -> False")
        return False
    rv = _ShowWindow(hwnd, SW_HIDE)
    _debug_log(f"hide(): ShowWindow(0x{hwnd:X}, SW_HIDE) returned {rv}")
    return True


def restore() -> bool:
    """ShowWindow(SW_RESTORE) + SetForegroundWindow. True iff hwnd was located."""
    hwnd = _find_hwnd()
    if not hwnd:
        _debug_log("restore(): _find_hwnd returned None -> False")
        return False
    rv1 = _ShowWindow(hwnd, SW_RESTORE)
    rv2 = _SetForegroundWindow(hwnd)
    _debug_log(f"restore(): ShowWindow(SW_RESTORE)={rv1} "
               f"SetForegroundWindow={rv2}")
    return True
