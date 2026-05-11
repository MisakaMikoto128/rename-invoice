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
    from PIL import Image, ImageDraw
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
