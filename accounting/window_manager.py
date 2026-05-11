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
