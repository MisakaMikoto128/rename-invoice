"""Window state-machine: minimize/close routing, hide-to-tray, dialog gate.

The dialog itself lives in `accounting/ui/dialogs.py` and is imported lazily
to avoid pulling Flet/UI symbols when WindowManager is unit-tested.

Hide/restore uses Win32 ShowWindow directly (via _win32_window) because
Flet 0.85's property-based minimize/restore is unreliable -- the window
gets stuck minimized with no taskbar entry. See _win32_window for details.
"""
from __future__ import annotations

from typing import Callable

from accounting import _win32_window, settings


class WindowManager:
    def __init__(self, page, on_real_quit: Callable[[], None]):
        self.page = page
        self.on_real_quit = on_real_quit
        self._closing = False

    def hide_to_tray(self) -> None:
        # Primary path: Win32 ShowWindow(SW_HIDE) — truly hides the window,
        # removes from taskbar AND Alt-Tab. The standard Windows tray-app
        # mechanism. Lookup is by PID-enumeration (not title) for robustness.
        if _win32_window.hide():
            return
        # Fallback (best-effort, may not fully hide on Flet 0.85)
        self.page.window.skip_task_bar = True
        self.page.window.minimized = True
        self.page.window.update()

    def show_from_tray(self) -> None:
        if self._closing:
            return
        # Win32 SW_RESTORE handles all states (hidden / minimized / normal)
        # and SetForegroundWindow brings it to focus.
        if _win32_window.restore():
            return
        # Fallback path for non-Windows / hwnd lookup failure
        self.page.window.skip_task_bar = False
        self.page.window.update()
        self.page.window.minimized = False
        self.page.window.update()
        self.page.run_task(self.page.window.to_front)

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.on_real_quit()
        # Flet 0.85: window.destroy() is async — calling it synchronously
        # returns an unawaited coroutine and the window never actually closes.
        # Schedule it on the event loop instead.
        self.page.run_task(self.page.window.destroy)

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
