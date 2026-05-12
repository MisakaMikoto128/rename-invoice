from unittest.mock import MagicMock, patch
import pytest

from accounting import _win32_window, window_manager, settings


@pytest.fixture
def mock_page():
    """A page mock with the window attributes WindowManager touches."""
    p = MagicMock()
    p.window.skip_task_bar = False
    p.window.minimized = False
    p.title = "test-window"
    return p


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_settings_path",
                         lambda: tmp_path / "settings.json")


@pytest.fixture(autouse=True)
def _stub_win32(monkeypatch):
    """Default: pretend Win32 hide/restore succeeded so the fallback path
    isn't exercised. Individual tests can override these mocks."""
    monkeypatch.setattr(_win32_window, "hide", lambda: True)
    monkeypatch.setattr(_win32_window, "restore", lambda: True)


def test_hide_to_tray_calls_win32_hide(mock_page, monkeypatch):
    spy = MagicMock(return_value=True)
    monkeypatch.setattr(_win32_window, "hide", spy)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm.hide_to_tray()
    spy.assert_called_once_with()


def test_hide_to_tray_falls_back_to_flet_properties_if_win32_fails(
        mock_page, monkeypatch):
    monkeypatch.setattr(_win32_window, "hide", lambda: False)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm.hide_to_tray()
    assert mock_page.window.skip_task_bar is True
    assert mock_page.window.minimized is True
    mock_page.window.update.assert_called()


def test_show_from_tray_calls_win32_restore(mock_page, monkeypatch):
    spy = MagicMock(return_value=True)
    monkeypatch.setattr(_win32_window, "restore", spy)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm.show_from_tray()
    spy.assert_called_once_with()


def test_show_from_tray_falls_back_if_win32_fails(mock_page, monkeypatch):
    monkeypatch.setattr(_win32_window, "restore", lambda: False)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    mock_page.window.minimized = True
    mock_page.window.skip_task_bar = True
    wm.show_from_tray()
    assert mock_page.window.minimized is False
    assert mock_page.window.skip_task_bar is False
    mock_page.run_task.assert_any_call(mock_page.window.to_front)


def test_quit_calls_cleanup_then_destroys_window(mock_page):
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    wm.quit()
    cleanup.assert_called_once()
    # destroy() is async; verify it's scheduled via run_task, not called sync.
    mock_page.run_task.assert_any_call(mock_page.window.destroy)


def test_quit_is_idempotent(mock_page):
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    wm.quit()
    wm.quit()
    cleanup.assert_called_once()
    # destroy scheduled exactly once across two quit() calls
    destroy_calls = [c for c in mock_page.run_task.call_args_list
                      if c.args == (mock_page.window.destroy,)]
    assert len(destroy_calls) == 1


def test_handle_close_action_hide_hides_without_dialog(mock_page, monkeypatch):
    settings.set_value(settings.KEY_CLOSE_ACTION, "hide")
    spy = MagicMock(return_value=True)
    monkeypatch.setattr(_win32_window, "hide", spy)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm._handle_close()
    spy.assert_called_once()


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


def test_on_window_event_minimize_hides_to_tray(mock_page, monkeypatch):
    spy = MagicMock(return_value=True)
    monkeypatch.setattr(_win32_window, "hide", spy)
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    evt = MagicMock(); evt.data = "minimize"
    wm.on_window_event(evt)
    spy.assert_called_once()


def test_on_window_event_close_routes_to_handle_close(mock_page):
    settings.set_value(settings.KEY_CLOSE_ACTION, "exit")
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    evt = MagicMock(); evt.data = "close"
    wm.on_window_event(evt)
    cleanup.assert_called_once()
