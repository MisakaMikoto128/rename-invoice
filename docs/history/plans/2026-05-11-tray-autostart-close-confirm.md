# Tray / Autostart / Close-Confirm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 AccountManager 加 QQ/微信级别的常驻型行为——系统托盘、首次关闭确认、开机自启、单实例。

**Architecture:** 4 个新模块（`tray.py` / `single_instance.py` / `autostart.py` / `window_manager.py`）+ 现有 `dialogs.py` 扩展 + `app.py` 集成。pystray 跑在守护线程，单实例 socket 跑在守护线程，两者通过 Flet 的 `page.run_thread()` 把回调 marshal 回主线程。

**Tech Stack:** Flet 0.85（已用）、pystray>=0.19（新）、Pillow>=10（新，pystray 依赖）、`winreg` / `socket` 标准库、pytest（已用）。

**Spec:** `docs/superpowers/specs/2026-05-11-tray-autostart-close-confirm-design.md`

---

## File Structure

```
accounting/
├─ settings.py             [MODIFY] 加 2 个 KEY 常量
├─ single_instance.py      [CREATE] socket 占座 + 唤起
├─ autostart.py            [CREATE] winreg 写 Run 键
├─ window_manager.py       [CREATE] hide/show + close-dialog 状态机
├─ tray.py                 [CREATE] pystray 守护线程封装
└─ ui/
   ├─ app.py               [MODIFY] 集成 4 个新模块
   └─ dialogs.py           [MODIFY] 关闭确认 + 关于 + 设置页扩展

tests/
├─ test_settings.py        [MODIFY] 加 2 条默认值测试
├─ test_single_instance.py [CREATE]
├─ test_autostart.py       [CREATE]
└─ test_window_manager.py  [CREATE]

requirements.txt           [MODIFY] +pystray +Pillow
build.py                   [MODIFY] +--add-data 图标 +hidden-import
BUILD.md                   [MODIFY] 大小预期 + smoke checklist
```

文件职责单一：每个新模块 60–120 行，不互相 import（`window_manager` 只 import `settings`；`tray` / `single_instance` / `autostart` 对应用零依赖，只暴露回调接口）。

---

### Task 1: 设置层加 2 个新 KEY 常量

**Files:**
- Modify: `accounting/settings.py:44-55` (KEY 常量段)
- Modify: `tests/test_settings.py`

- [ ] **Step 1: 加默认值测试**

在 `tests/test_settings.py` 末尾追加：

```python
def test_close_action_default_is_ask():
    assert settings.get(settings.KEY_CLOSE_ACTION, "ask") == "ask"


def test_autostart_enabled_default_is_off():
    assert settings.get(settings.KEY_AUTOSTART_ENABLED, "0") == "0"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_settings.py -v`
Expected: 2 个新测试 FAIL，`AttributeError: module 'accounting.settings' has no attribute 'KEY_CLOSE_ACTION'`

- [ ] **Step 3: 在 settings.py 加常量**

在 `accounting/settings.py` 末尾（`KEY_WINDOW_MAXIMIZED` 后）加：

```python
KEY_CLOSE_ACTION = "close_action"            # "ask" | "hide" | "exit"
KEY_AUTOSTART_ENABLED = "autostart_enabled"  # "0" | "1"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_settings.py -v`
Expected: 全部 PASS（原 6 个 + 新 2 个 = 8 passed）

- [ ] **Step 5: Commit**

```bash
git add accounting/settings.py tests/test_settings.py
git commit -m "feat(settings): add close_action and autostart_enabled keys"
```

---

### Task 2: `single_instance.py` — socket 占座 + 唤起

**Files:**
- Create: `accounting/single_instance.py`
- Create: `tests/test_single_instance.py`

- [ ] **Step 1: 写失败测试**

`tests/test_single_instance.py`:

```python
import socket
from unittest.mock import MagicMock, patch
import pytest

from accounting import single_instance


def _mock_socket_class(behaviors: list):
    """behaviors: list of dicts per call to socket.socket().
    Each dict can have 'bind_error' (OSError) and/or 'connect_error' (OSError).
    """
    calls = iter(behaviors)
    instances = []

    def factory(*args, **kwargs):
        m = MagicMock()
        b = next(calls, {})
        if b.get("bind_error"):
            m.bind.side_effect = b["bind_error"]
        if b.get("connect_error"):
            m.connect.side_effect = b["connect_error"]
        instances.append(m)
        return m

    return factory, instances


def test_acquire_when_port_free_returns_listening_sock():
    factory, instances = _mock_socket_class([{}])  # bind 成功
    with patch.object(socket, "socket", side_effect=factory):
        sock = single_instance.acquire_or_signal_existing()
    assert sock is not None
    assert sock is instances[0]
    instances[0].bind.assert_called_once_with(("127.0.0.1", single_instance.PORT))


def test_acquire_when_port_held_by_peer_sends_show_and_returns_none():
    factory, instances = _mock_socket_class([
        {"bind_error": OSError(10048, "in use")},  # 第一个 socket: bind 失败
        {},                                         # 第二个 socket: connect 成功
    ])
    with patch.object(socket, "socket", side_effect=factory):
        sock = single_instance.acquire_or_signal_existing()
    assert sock is None
    instances[1].connect.assert_called_once_with(("127.0.0.1", single_instance.PORT))
    instances[1].sendall.assert_called_once_with(b"SHOW\n")


def test_acquire_when_port_blocked_by_other_process_degrades():
    factory, instances = _mock_socket_class([
        {"bind_error": OSError(10048, "in use")},  # 第一个: bind 47821 失败
        {"connect_error": OSError("refused")},      # 第二个: connect 失败
        {},                                         # 第三个: bind port 0 成功
    ])
    with patch.object(socket, "socket", side_effect=factory):
        sock = single_instance.acquire_or_signal_existing()
    # 单实例保护降级,但仍返回一个 sock(应用继续启动)
    assert sock is instances[2]
    instances[2].bind.assert_called_once_with(("127.0.0.1", 0))


def test_serve_show_requests_calls_on_show_on_recv():
    on_show = MagicMock()
    sock = MagicMock()
    conn = MagicMock()
    conn.recv.return_value = b"SHOW\n"
    # accept() 一次返回 conn,再次抛 OSError 让 listener 退出
    sock.accept.side_effect = [(conn, ("127.0.0.1", 12345)), OSError("stopped")]

    single_instance._listener_loop(sock, on_show)  # 直接同步跑,不起线程

    on_show.assert_called_once()
    conn.close.assert_called_once()


def test_serve_show_requests_ignores_non_show_payload():
    on_show = MagicMock()
    sock = MagicMock()
    conn = MagicMock()
    conn.recv.return_value = b"PING\n"
    sock.accept.side_effect = [(conn, ("127.0.0.1", 12345)), OSError("stopped")]

    single_instance._listener_loop(sock, on_show)

    on_show.assert_not_called()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_single_instance.py -v`
Expected: `ModuleNotFoundError: No module named 'accounting.single_instance'`

- [ ] **Step 3: 实现 `single_instance.py`**

`accounting/single_instance.py`:

```python
"""Single-instance enforcement via a 127.0.0.1 socket on a fixed port.

The port serves two purposes: it is the mutex (only one process can bind),
and it is the IPC channel (second-launch sends "SHOW" to make the first
process bring its window forward). No new dependencies, no lock files.
"""
from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

PORT = 47821  # 本地回环固定端口, 选个不冲突的


def acquire_or_signal_existing() -> Optional[socket.socket]:
    """尝试占座 127.0.0.1:PORT。

    返回:
        - 占座成功 → 已 bind 的 socket (调用方负责 listen + serve_show_requests)
        - 占座失败但能 connect 上 → 发 b"SHOW\\n",返回 None (调用方 sys.exit)
        - 占座失败且 connect 不上 → log warning,bind 随机端口降级,返回那个 sock
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PORT))
        return sock
    except OSError:
        # 端口被占,尝试当 peer 处理
        try:
            sock.close()
        except OSError:
            pass

        peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            peer.connect(("127.0.0.1", PORT))
            peer.sendall(b"SHOW\n")
            peer.close()
            return None
        except OSError as e:
            log.warning("single-instance: port %d held by non-peer (%s); "
                        "degrading to random port", PORT, e)
            try:
                peer.close()
            except OSError:
                pass
            degraded = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            degraded.bind(("127.0.0.1", 0))
            return degraded


def serve_show_requests(sock: socket.socket, on_show: Callable[[], None]) -> None:
    """Listen on `sock` in a daemon thread. Calls `on_show()` per "SHOW" line."""
    sock.listen(5)
    t = threading.Thread(target=_listener_loop, args=(sock, on_show),
                         daemon=True, name="single-instance-listener")
    t.start()


def _listener_loop(sock: socket.socket, on_show: Callable[[], None]) -> None:
    """Internal: accept loop. Exits on socket close / OSError."""
    while True:
        try:
            conn, _addr = sock.accept()
        except OSError:
            return  # socket closed
        try:
            data = conn.recv(1024)
            if data and b"SHOW" in data:
                on_show()
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_single_instance.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add accounting/single_instance.py tests/test_single_instance.py
git commit -m "feat(single-instance): socket-based mutex + SHOW signal"
```

---

### Task 3: `autostart.py` — winreg 写 Run 键

**Files:**
- Create: `accounting/autostart.py`
- Create: `tests/test_autostart.py`

- [ ] **Step 1: 写失败测试**

`tests/test_autostart.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# winreg 只在 Windows 上存在; 测试用 mock 替代
if sys.platform != "win32":
    pytest.skip("Windows-only", allow_module_level=True)

from accounting import autostart


@pytest.fixture
def fake_winreg(monkeypatch):
    m = MagicMock()
    # OpenKey 返回一个 context-manager-like 句柄
    handle = MagicMock()
    handle.__enter__ = MagicMock(return_value=handle)
    handle.__exit__ = MagicMock(return_value=False)
    m.OpenKey.return_value = handle
    m.CreateKey.return_value = handle
    m.HKEY_CURRENT_USER = "HKCU"
    m.KEY_READ = 0x20019
    m.KEY_WRITE = 0x20006
    m.REG_SZ = 1
    monkeypatch.setattr(autostart, "winreg", m)
    return m


def test_enable_writes_exe_path_with_silent_flag(fake_winreg):
    autostart.enable(Path(r"C:\Apps\AccountManager.exe"))
    fake_winreg.SetValueEx.assert_called_once()
    args, _ = fake_winreg.SetValueEx.call_args
    # 签名: SetValueEx(key, value_name, reserved, type, value)
    assert args[1] == autostart.APP_NAME
    assert args[3] == fake_winreg.REG_SZ
    assert args[4] == r'"C:\Apps\AccountManager.exe" --silent'


def test_disable_calls_delete_value(fake_winreg):
    autostart.disable()
    fake_winreg.DeleteValue.assert_called_once()
    args, _ = fake_winreg.DeleteValue.call_args
    assert args[1] == autostart.APP_NAME


def test_disable_swallows_missing_value_error(fake_winreg):
    fake_winreg.DeleteValue.side_effect = FileNotFoundError()
    # 不应抛
    autostart.disable()


def test_is_enabled_true_when_value_exists(fake_winreg):
    fake_winreg.QueryValueEx.return_value = (r'"X" --silent', 1)
    assert autostart.is_enabled() is True


def test_is_enabled_false_when_value_missing(fake_winreg):
    fake_winreg.QueryValueEx.side_effect = FileNotFoundError()
    assert autostart.is_enabled() is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: `ModuleNotFoundError: No module named 'accounting.autostart'`

- [ ] **Step 3: 实现 `autostart.py`**

`accounting/autostart.py`:

```python
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
    """Write the Run-key entry. Value = quoted exe path + ' --silent'.

    Raises OSError on permission failure (caller surfaces a UI error).
    """
    if winreg is None:
        raise OSError("autostart is only supported on Windows")
    value = f'"{exe_path}" --silent'
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add accounting/autostart.py tests/test_autostart.py
git commit -m "feat(autostart): HKCU Run-key enable/disable"
```

---

### Task 4: `window_manager.py` — close-dialog 状态机

**Files:**
- Create: `accounting/window_manager.py`
- Create: `tests/test_window_manager.py`

- [ ] **Step 1: 写失败测试**

`tests/test_window_manager.py`:

```python
from unittest.mock import MagicMock, patch
import pytest

from accounting import window_manager, settings


@pytest.fixture
def mock_page():
    """A page mock with the window attributes WindowManager touches."""
    p = MagicMock()
    p.window.visible = True
    p.window.skip_task_bar = False
    return p


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_settings_path",
                         lambda: tmp_path / "settings.json")


def test_hide_to_tray_sets_invisible_and_skip_taskbar(mock_page):
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm.hide_to_tray()
    assert mock_page.window.visible is False
    assert mock_page.window.skip_task_bar is True
    mock_page.update.assert_called()


def test_show_from_tray_sets_visible_and_brings_to_front(mock_page):
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    mock_page.window.visible = False
    mock_page.window.skip_task_bar = True
    wm.show_from_tray()
    assert mock_page.window.visible is True
    assert mock_page.window.skip_task_bar is False
    mock_page.window.to_front.assert_called_once()


def test_quit_calls_cleanup_then_destroys_window(mock_page):
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    wm.quit()
    cleanup.assert_called_once()
    mock_page.window.destroy.assert_called_once()


def test_quit_is_idempotent(mock_page):
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    wm.quit()
    wm.quit()
    cleanup.assert_called_once()
    assert mock_page.window.destroy.call_count == 1


def test_handle_close_action_hide_hides_without_dialog(mock_page):
    settings.set_value(settings.KEY_CLOSE_ACTION, "hide")
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm._handle_close()
    assert mock_page.window.visible is False


def test_handle_close_action_exit_quits_without_dialog(mock_page):
    settings.set_value(settings.KEY_CLOSE_ACTION, "exit")
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    wm._handle_close()
    cleanup.assert_called_once()


def test_handle_close_action_ask_shows_dialog(mock_page, monkeypatch):
    settings.set_value(settings.KEY_CLOSE_ACTION, "ask")
    spy = MagicMock()
    monkeypatch.setattr(window_manager, "show_close_confirm_dialog", spy)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm._handle_close()
    spy.assert_called_once()


def test_on_window_event_minimize_hides_to_tray(mock_page):
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    evt = MagicMock(); evt.data = "minimize"
    wm.on_window_event(evt)
    assert mock_page.window.visible is False
    assert mock_page.window.skip_task_bar is True


def test_on_window_event_close_routes_to_handle_close(mock_page):
    settings.set_value(settings.KEY_CLOSE_ACTION, "exit")
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    evt = MagicMock(); evt.data = "close"
    wm.on_window_event(evt)
    cleanup.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_window_manager.py -v`
Expected: `ModuleNotFoundError: No module named 'accounting.window_manager'`

- [ ] **Step 3: 实现 `window_manager.py`**

`accounting/window_manager.py`:

```python
"""Window state-machine: minimize/close routing, hide-to-tray, dialog gate.

The dialog itself lives in `accounting/ui/dialogs.py` and is imported lazily
to avoid pulling Flet/UI symbols when WindowManager is unit-tested.
"""
from __future__ import annotations

from typing import Callable

from accounting import settings


class WindowManager:
    def __init__(self, page, on_real_quit: Callable[[], None]):
        self.page = page
        self.on_real_quit = on_real_quit
        self._closing = False

    def hide_to_tray(self) -> None:
        self.page.window.visible = False
        self.page.window.skip_task_bar = True
        self.page.update()

    def show_from_tray(self) -> None:
        if self._closing:
            return
        self.page.window.skip_task_bar = False
        self.page.window.visible = True
        self.page.window.to_front()
        self.page.update()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.on_real_quit()
        self.page.window.destroy()

    def on_window_event(self, e) -> None:
        if e.data == "minimize":
            self.hide_to_tray()
        elif e.data == "close":
            self._handle_close()

    def _handle_close(self) -> None:
        action = settings.get(settings.KEY_CLOSE_ACTION, "ask")
        if action == "hide":
            self.hide_to_tray()
            return
        if action == "exit":
            self.quit()
            return
        # action == "ask"
        show_close_confirm_dialog(
            self.page,
            on_hide=self._on_dialog_hide,
            on_quit=self._on_dialog_quit,
        )

    def _on_dialog_hide(self, remember: bool) -> None:
        if remember:
            settings.set_value(settings.KEY_CLOSE_ACTION, "hide")
        self.hide_to_tray()

    def _on_dialog_quit(self, remember: bool) -> None:
        if remember:
            settings.set_value(settings.KEY_CLOSE_ACTION, "exit")
        self.quit()


def show_close_confirm_dialog(page, on_hide: Callable[[bool], None],
                               on_quit: Callable[[bool], None]) -> None:
    """Indirection point so tests can monkeypatch without importing Flet.

    The real implementation lives in accounting/ui/dialogs.py and is bound
    at import time when the UI layer is loaded.
    """
    from accounting.ui.dialogs import show_close_confirm_dialog as _impl
    _impl(page, on_hide, on_quit)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_window_manager.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add accounting/window_manager.py tests/test_window_manager.py
git commit -m "feat(window-manager): minimize/close routing + dialog state machine"
```

---

### Task 5: `tray.py` — pystray 守护线程封装

**No unit tests** — pystray 启不起后端进程在 CI 环境（per spec §8.2）。逻辑通过 Task 8 的手动 smoke 测试覆盖。

**Files:**
- Create: `accounting/tray.py`
- Modify: `requirements.txt`（先加 pystray 才能 import）

- [ ] **Step 1: 加运行时依赖到 requirements.txt**

修改 `requirements.txt`：

```
# Runtime dependencies (end-user, source mode)
# Install: pip install -r requirements.txt

# PDF text extraction (CLI: rename_invoice.py)
pymupdf>=1.24.0,<2.0

# xlsx summary export (CLI --xlsx, GUI export)
openpyxl>=3.1.0,<4.0

# Desktop GUI (accounting/ui)
# Lower bound = tested version; 0.21..0.84 have breaking API differences
# (ft.app -> ft.run, Dropdown.on_change -> on_select, snack_bar API, ...)
flet>=0.85,<1.0

# System tray icon (accounting/tray.py); Pillow is a pystray dependency
# we list explicitly to pin a version range.
pystray>=0.19,<1.0
Pillow>=10.0,<12.0
```

- [ ] **Step 2: 安装新依赖**

Run: `pip install pystray>=0.19 "Pillow>=10.0,<12.0"`
Expected: 成功安装

- [ ] **Step 3: 实现 `tray.py`**

`accounting/tray.py`:

```python
"""System-tray icon controller wrapping pystray.

The icon runs in its own daemon thread; callbacks must NOT touch Flet's page
directly — the caller is expected to wrap each callback with
`page.run_thread(...)` to marshal back to the main loop.
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)


def _resource_path(rel: str) -> Path:
    """Resolve a bundled resource (icon-256.png) in both onefile and source modes."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    # source mode: project root is two levels up from this file
    return Path(__file__).resolve().parent.parent / rel


def _load_icon_image():
    """Return a PIL.Image for the tray icon. Falls back to a synthesized 32x32."""
    from PIL import Image, ImageDraw, ImageFont
    path = _resource_path("assets/icon-256.png")
    if path.exists():
        try:
            return Image.open(path)
        except OSError as e:
            log.warning("tray: icon load failed (%s); using fallback", e)
    img = Image.new("RGB", (32, 32), color=(40, 60, 110))
    draw = ImageDraw.Draw(img)
    draw.text((10, 6), "A", fill=(255, 255, 255))
    return img


class TrayController:
    def __init__(self,
                 on_show: Callable[[], None],
                 on_settings: Callable[[], None],
                 on_about: Callable[[], None],
                 on_quit: Callable[[], None]) -> None:
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_about = on_about
        self.on_quit = on_quit
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start the tray icon in a daemon thread. Returns True if started OK."""
        try:
            import pystray
            from pystray import MenuItem as Item, Menu
        except Exception as e:
            log.warning("tray: pystray unavailable (%s); skipping", e)
            return False

        image = _load_icon_image()
        menu = Menu(
            Item("显示主界面", lambda icon, item: self.on_show(), default=True),
            Item("设置...", lambda icon, item: self.on_settings()),
            Item("关于", lambda icon, item: self.on_about()),
            Menu.SEPARATOR,
            Item("退出", lambda icon, item: self.on_quit()),
        )
        self._icon = pystray.Icon("AccountManager", image,
                                  "AccountManager", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True,
                                         name="tray-icon")
        try:
            self._thread.start()
            return True
        except Exception as e:
            log.warning("tray: failed to start (%s)", e)
            return False

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
```

- [ ] **Step 4: 烟测：能 import 不报错，能 start 不抛**

Run（PowerShell）:

```powershell
python -c "from accounting.tray import TrayController; c = TrayController(lambda: None, lambda: None, lambda: None, lambda: None); ok = c.start(); print('started=', ok); import time; time.sleep(1); c.stop(); print('stopped')"
```

Expected: 输出 `started= True` 然后 `stopped`，过程中 Windows 通知区出现一个图标 1 秒后消失。如果图标没出来但 `started=True` 也算过——可能 Windows 通知区折叠了，右键展开能看到。

- [ ] **Step 5: 现有测试不挂**

Run: `python -m pytest tests/ -q`
Expected: 全绿（之前 86 + 新加的 ~19 ≈ 105 passed）

- [ ] **Step 6: Commit**

```bash
git add accounting/tray.py requirements.txt
git commit -m "feat(tray): pystray-based system tray with 4-item menu"
```

---

### Task 6: 扩展 `dialogs.py` — 关闭确认 + 关于 + 设置页

**Files:**
- Modify: `accounting/ui/dialogs.py` (在文件末尾追加 + 改 `show_settings_dialog`)

- [ ] **Step 1: 加「关闭确认」对话框**

在 `accounting/ui/dialogs.py` 末尾追加：

```python
def show_close_confirm_dialog(page: ft.Page,
                               on_hide: Callable[[bool], None],
                               on_quit: Callable[[bool], None]) -> None:
    """First-time close confirm. on_hide / on_quit receive `remember: bool`.

    Buttons: [隐藏到托盘] (primary) / [退出] / [取消].
    Checkbox: [☑ 记住本次选择] (default checked).
    """
    remember_cb = ft.Checkbox(label="记住本次选择(可在设置里修改)", value=True)

    def click_hide(_e):
        page.pop_dialog()
        on_hide(bool(remember_cb.value))

    def click_quit(_e):
        page.pop_dialog()
        on_quit(bool(remember_cb.value))

    def click_cancel(_e):
        page.pop_dialog()

    dialog = ft.AlertDialog(
        title=ft.Text("关闭 AccountManager"),
        content=ft.Column([
            ft.Text("关闭主窗口后, 应用继续在系统托盘运行吗?"),
            ft.Container(height=8),
            remember_cb,
        ], tight=True, width=420, height=110),
        actions=[
            ft.TextButton("取消", on_click=click_cancel),
            ft.TextButton("退出", on_click=click_quit),
            ft.ElevatedButton("隐藏到托盘", on_click=click_hide),
        ],
    )
    page.show_dialog(dialog)
```

- [ ] **Step 2: 加「关于」对话框**

在 `accounting/ui/dialogs.py` 末尾追加：

```python
def show_about_dialog(page: ft.Page, version: str = "1.0.2") -> None:
    """Static About box. Version string supplied by caller."""
    content = ft.Column([
        ft.Text(f"AccountManager v{version}", weight=ft.FontWeight.BOLD),
        ft.Container(height=4),
        ft.Text("发票批量管理 / 报销账目跟踪", size=12),
        ft.Container(height=12),
        ft.Text("GitHub: github.com/MisakaMikoto128/rename-invoice",
                size=12, color=ft.Colors.OUTLINE, selectable=True),
        ft.Text("Licensed under MIT", size=11, color=ft.Colors.OUTLINE),
    ], tight=True, width=400, height=140)

    dialog = ft.AlertDialog(
        title=ft.Text("关于"),
        content=content,
        actions=[
            ft.TextButton("关闭", on_click=lambda _e: page.pop_dialog()),
        ],
    )
    page.show_dialog(dialog)
```

- [ ] **Step 3: 改 `show_settings_dialog` 加两项**

定位 `show_settings_dialog` 函数（约在 dialogs.py:64）。在 `theme_switch.on_change = on_theme_change` 之后、`def trigger_migrate` 之前插入：

```python
    # --- 行为 (close action + autostart) ---
    from accounting import autostart as _autostart

    close_options = [
        ft.dropdown.Option("ask", "询问"),
        ft.dropdown.Option("hide", "隐藏到托盘"),
        ft.dropdown.Option("exit", "直接退出"),
    ]
    current_close = _settings.get(_settings.KEY_CLOSE_ACTION, "ask")
    close_dd = ft.Dropdown(label="关闭时", value=current_close,
                            options=close_options, width=240)

    def on_close_change(_e):
        _settings.set_value(_settings.KEY_CLOSE_ACTION, close_dd.value or "ask")

    close_dd.on_change = on_close_change

    autostart_switch = ft.Switch(label="开机启动",
                                  value=_autostart.is_enabled())

    def on_autostart_change(_e):
        try:
            if autostart_switch.value:
                _autostart.enable(_autostart.current_exe_path())
            else:
                _autostart.disable()
            _settings.set_value(
                _settings.KEY_AUTOSTART_ENABLED,
                "1" if autostart_switch.value else "0",
            )
        except OSError as ex:
            # 回退开关 + 通知用户
            autostart_switch.value = not autostart_switch.value
            page.show_dialog(ft.SnackBar(
                content=ft.Text(f"开机启动设置失败: {ex}")))
            page.update()

    autostart_switch.on_change = on_autostart_change
```

然后修改 `ft.AlertDialog` 的 content `ft.Column` 列表——在 `theme_switch` 后、`ft.Container(height=12)` 前插入两行：

```python
            ft.Text("行为", weight=ft.FontWeight.BOLD),
            close_dd,
            autostart_switch,
            ft.Container(height=12),
```

同时把 content `ft.Column` 的 `height=270` 改成 `height=380`（让新增内容显示完整）。

- [ ] **Step 4: 手动 smoke**

Run（PowerShell）:

```powershell
python -m accounting.ui.app
```

操作：菜单 → 设置 → 看「关闭时」下拉和「开机启动」开关。改下拉、切开关，关掉再开应用，看是否记住状态。
Expected: 下拉默认「询问」，开关默认「关闭」；设置后重启应用，下拉记得上次选择。开关切开启时检查任务管理器→启动应用列表，看到「AccountManager」。

- [ ] **Step 5: 现有测试不挂**

Run: `python -m pytest tests/ -q`
Expected: 全绿

- [ ] **Step 6: Commit**

```bash
git add accounting/ui/dialogs.py
git commit -m "feat(ui): close-confirm + about dialogs + settings page extensions"
```

---

### Task 7: 集成 `app.py`

**Files:**
- Modify: `accounting/ui/app.py`

- [ ] **Step 1: 改 `main(page)` 签名 + entry point**

完整重写 `accounting/ui/app.py` 的开头部分（imports + `main()` 上半部分 + 底部 entry point）。保留 `render_main / render_project / render_trash` 不动。

把文件顶部到 `def render_main():` 之前的所有内容（约 1–70 行）替换成：

```python
"""Flet entry. Routes between main_view and project_view."""
import socket
import sys
from typing import Optional

import flet as ft

from accounting import db, settings, single_instance
from accounting.tray import TrayController
from accounting.ui.main_view import build_main_view
from accounting.ui.project_view import build_project_view
from accounting.ui.state import AppState
from accounting.window_manager import WindowManager


# Wired up in __main__ block; main() reads them via closure.
_LISTENER_SOCK: Optional[socket.socket] = None
_SILENT_FLAG: bool = False


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.prevent_close = True  # ← 必须;否则 ✕ 直接销毁窗口

    # Defaults — overridden below if user has saved window state.
    page.window.width = 1200
    page.window.height = 720
    saved_theme = settings.get(settings.KEY_THEME_MODE, "light")
    page.theme_mode = (ft.ThemeMode.DARK if saved_theme == "dark"
                       else ft.ThemeMode.LIGHT)
    page.padding = 0

    # Restore window size + position from saved settings (best-effort).
    try:
        w = settings.get(settings.KEY_WINDOW_WIDTH)
        h = settings.get(settings.KEY_WINDOW_HEIGHT)
        left = settings.get(settings.KEY_WINDOW_LEFT)
        top = settings.get(settings.KEY_WINDOW_TOP)
        maxi = settings.get(settings.KEY_WINDOW_MAXIMIZED)
        if w:
            page.window.width = float(w)
        if h:
            page.window.height = float(h)
        if left is not None:
            page.window.left = float(left)
        if top is not None:
            page.window.top = float(top)
        if maxi == "1":
            page.window.maximized = True
    except Exception:
        pass  # corrupt settings — fall back to defaults

    state = AppState(db_path=str(db.default_db_path()))
    state.init()

    def save_window_state():
        try:
            if page.window.width:
                settings.set_value(settings.KEY_WINDOW_WIDTH,
                                   str(page.window.width))
            if page.window.height:
                settings.set_value(settings.KEY_WINDOW_HEIGHT,
                                   str(page.window.height))
            if page.window.left is not None:
                settings.set_value(settings.KEY_WINDOW_LEFT,
                                   str(page.window.left))
            if page.window.top is not None:
                settings.set_value(settings.KEY_WINDOW_TOP,
                                   str(page.window.top))
            settings.set_value(
                settings.KEY_WINDOW_MAXIMIZED,
                "1" if page.window.maximized else "0",
            )
        except Exception:
            pass

    tray: Optional[TrayController] = None  # 前置声明给 cleanup 闭包

    def cleanup():
        save_window_state()
        state.close()
        if tray is not None:
            tray.stop()

    wm = WindowManager(page, on_real_quit=cleanup)

    container = ft.Container(expand=True)

    # ---- Tray wiring (after container created so render_main can be called) ----
    def from_tray(fn):
        """Wrap a tray-thread callback so it runs on the Flet main thread."""
        return lambda: page.run_thread(fn)

    def tray_show():
        wm.show_from_tray()

    def tray_settings():
        wm.show_from_tray()
        _open_settings_top_level()      # forward decl, see below

    def tray_about():
        from accounting.ui.dialogs import show_about_dialog
        wm.show_from_tray()
        show_about_dialog(page)

    def tray_quit():
        wm.quit()

    tray = TrayController(
        on_show=from_tray(tray_show),
        on_settings=from_tray(tray_settings),
        on_about=from_tray(tray_about),
        on_quit=from_tray(tray_quit),
    )
    tray.start()

    # ---- Single-instance listener (if we hold the lock) ----
    if _LISTENER_SOCK is not None:
        single_instance.serve_show_requests(
            _LISTENER_SOCK,
            on_show=from_tray(wm.show_from_tray),
        )

    page.window.on_event = wm.on_window_event

    # Forward declaration: render_main defines this later via closure.
    _open_settings_holder: dict = {"fn": lambda: None}

    def _open_settings_top_level():
        _open_settings_holder["fn"]()
```

然后在 `render_main()` 函数体内（约改后的 80–90 行），定位到 `def open_settings():` 这一行**之后**、`def open_invoice_in_project(...)` 之前，插入：

```python
        # Expose to tray callback (which lives outside this scope)
        _open_settings_holder["fn"] = open_settings
```

最后在文件末尾的 `if __name__ == "__main__":` 块完整替换：

```python
if __name__ == "__main__":
    _SILENT_FLAG = "--silent" in sys.argv
    _LISTENER_SOCK = single_instance.acquire_or_signal_existing()
    if _LISTENER_SOCK is None:
        # 已有实例在跑且收到了我们的 SHOW;退出
        sys.exit(0)
    ft.run(main)
```

并且把 `main()` 末尾的 `render_main()` 调用改成：

```python
    page.add(container)
    if _SILENT_FLAG:
        wm.hide_to_tray()
    render_main()
```

- [ ] **Step 2: 现有测试不挂**

Run: `python -m pytest tests/ -q`
Expected: 全绿。`test_ui_state.py` / `test_ui_widgets.py` 不应受影响。

- [ ] **Step 3: 源码模式手动 smoke (短跑)**

Run（PowerShell）:

```powershell
python -m accounting.ui.app
```

Expected:
- 主窗弹出，托盘出现 AccountManager 图标。
- 点 ─ 最小化 → 主窗消失，任务栏按钮消失，托盘仍在。
- 左键托盘图标 → 主窗弹回。
- 点 ✕ → 弹「关闭确认」对话框（默认 close_action="ask"）。
- 选「退出」+ 勾「记住」→ 进程退出。
- 重启 `python -m accounting.ui.app` → 点 ✕ 直接退出，不弹对话框。

如果某一步不通过，回退到对应模块单测查问题。

- [ ] **Step 4: 重置 close_action 给下游测试一个干净起点**

打开主窗 → 设置 → 关闭时 → 改回「询问」→ 关掉应用。

- [ ] **Step 5: Commit**

```bash
git add accounting/ui/app.py
git commit -m "feat(app): wire tray + single-instance + window-manager into Flet main"
```

---

### Task 8: 打包脚本 + BUILD.md + 端到端 smoke

**Files:**
- Modify: `build.py`
- Modify: `BUILD.md`

- [ ] **Step 1: 改 `build.py`**

在 `build.py` 的 `cmd` 列表里（约第 147–158 行的 `cmd: list[str] = [...]`），在 `"-y",` 之前插入 `--add-data` 和 `--hidden-import`：

```python
        "--add-data", f"{SCRIPT_DIR / 'assets' / 'icon-256.png'};assets",
        "--hidden-import", "pystray._win32",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "-y",
```

注意 PyInstaller `--add-data` 在 Windows 上分隔符是 `;`。

确认 `EXCLUDES` 列表（约第 47–55 行）里**没有** `PIL` / `Pillow` / `pillow`。如果有，删掉。当前 spec 看 build.py 已经没有这些条目——确认即可。

更新 docstring（文件顶部 `Output:` 注释）：

把 `release/v<version>/AccountManager.exe   (~75 MB, single-file)` 改成 `release/v<version>/AccountManager.exe   (~80 MB, single-file)`。

- [ ] **Step 2: 改 BUILD.md**

定位 BUILD.md 中关于 size 的两处描述：

替换 `~75 MB, single-file` → `~80 MB, single-file`（出现 2 次：第 14 行附近 + 文件末尾对比表中的 PyInstaller 行）。

替换第 33 行 `28 \`--pyinstaller-build-args=--exclude-module=...\` flags trimming the bundle from ~237 MB to ~75 MB` → `29 \`--pyinstaller-build-args=--exclude-module=...\` flags trimming the bundle from ~242 MB to ~80 MB`（pystray + Pillow 约 5 MB）。

在「Smoke test」段落（约第 54 行）的 PowerShell 块**之后**、「Known caveats」段落之前，插入新一段：

```markdown
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
```

- [ ] **Step 3: 跑一次打包**

Run（PowerShell）:

```powershell
.\build.bat
```

Expected: 大约 30–60 秒后输出 `[OK] Build complete.`，`release\v<version>\AccountManager.exe` 大小约 78–82 MB。

如果有 `WARNING: Hidden import "pystray._win32" not found` 报红——继续，运行时如果 tray 起不来再回头看；先看 smoke 第 1 步。

- [ ] **Step 4: 跑端到端 smoke（BUILD.md 第 1–10 条）**

完整按 BUILD.md 新加的 10 条 checklist 走一遍。每条 ✓ 即可继续下一条。

第 8 / 10 条需要重启电脑或注销重登 → 任务管理器→启动 tab 验证（不必真重启，只看 tab 里 entry 是否出现/消失）。

如某一步不通过：
- 步骤 1 失败（托盘图标没出来）→ 检查 `_resource_path` 是否解到 bundle 内的 icon-256.png；试试在 PowerShell 跑 `python -c "from accounting.tray import _load_icon_image; _load_icon_image().show()"` 看是不是 fallback 图像。
- 步骤 9 失败（启动了两个进程）→ 检查 `acquire_or_signal_existing()` 是否进入了「降级到随机端口」分支（log 会有 warning）；可能 47821 被别的程序占了。

- [ ] **Step 5: Commit**

```bash
git add build.py BUILD.md
git commit -m "build: bundle tray icon + add pystray hidden-imports + update smoke checklist"
```

---

### Task 9: 收尾——回归 + 文档

**Files:**
- 全仓库（只读检查）

- [ ] **Step 1: 全量回归测试**

Run: `python -m pytest tests/ -v`
Expected: 全绿。统计：~86 老测试 + Task 1–4 新增（2 + 5 + 5 + 9 = 21）≈ 107 passed。

如果任何老测试挂了，**不要继续**——回头看 Task 7 的集成改动是否破坏了别的引用。

- [ ] **Step 2: 检查 git status 干净**

Run: `git status`
Expected: `nothing to commit, working tree clean`。

- [ ] **Step 3: 看一眼 git log**

Run: `git log --oneline -10`
Expected: 看到 Task 1–8 的 8 个 commit，外加 spec doc commit (`ac5b568`)。顺序合理。

- [ ] **Step 4: 标记任务完成**

无新文件，无新 commit。整个特性的 acceptance criteria：
- ✓ 6 个新 / 改的 commit（settings keys / single_instance / autostart / window_manager / tray / dialogs / app / build）
- ✓ 21 个新单测全绿
- ✓ 10 条 smoke checklist 全绿
- ✓ release/v\<version\>/AccountManager.exe 实际可双击运行

完成后等用户决定是否合并到 main / 是否打 v1.0.2 tag。

---

## Self-Review Checklist

> （这是给 plan 作者的 sanity check，不是给执行者的步骤。）

**Spec coverage:**
- 目标 §1（托盘/最小化/关闭确认/自启/单实例）→ Task 5 (tray) + Task 4 (close+min) + Task 3 (autostart) + Task 2 (single instance)
- 范围 §2 不包含项 → 计划中不出现（macOS / 消息通知 / 全局快捷键 / 命令转发 / 启动延迟均未实现）✓
- 技术选型 §3 → 所有技术正确落地（pystray / 47821 socket / page.run_thread / HKCU\Run / 沿用 settings.json）✓
- 架构 §4 启动序列 → Task 7 完整复现
- 组件 5.1–5.5 → Tasks 2–7 一一对应
- 数据流 §6 5 个场景 → 全部由代码路径覆盖（启动/关闭/最小化/托盘菜单/二号实例），smoke 第 1/2/4/9 条端到端验
- 错误处理 §7 → tray 降级 / 自启 OSError 弹回 Switch / 单实例端口降级 / `_closing` 幂等全部在代码中
- 测试 §8 → Tasks 2–4 三个单测模块 + Task 5/6 手动 smoke + Task 8 完整 checklist
- 实施顺序 §9 → 计划任务顺序 1→2→3→4→5→6→7→8→9 = 基础 → 托盘 → UI → 集成 → 打包

**Placeholder scan:** 无 TBD / TODO。所有代码块都是可粘贴的完整代码。

**Type consistency:**
- `WindowManager.__init__(page, on_real_quit)` 在 Task 4 定义、Task 7 使用 → 一致 ✓
- `TrayController(on_show, on_settings, on_about, on_quit)` Task 5 定义、Task 7 使用 → 一致 ✓
- `single_instance.acquire_or_signal_existing()` 返回 `Optional[socket]` Task 2 定义、Task 7 使用 → 一致 ✓
- `settings.KEY_CLOSE_ACTION` Task 1 定义、Task 4 + Task 6 使用 → 一致 ✓
- `show_close_confirm_dialog(page, on_hide, on_quit)` Task 6 定义、Task 4 的 indirection 引用 → 签名一致 ✓
