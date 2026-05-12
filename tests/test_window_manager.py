from unittest.mock import MagicMock, patch
import pytest

from accounting import window_manager, settings


@pytest.fixture
def mock_page():
    """A page mock with the window attributes WindowManager touches."""
    p = MagicMock()
    p.window.skip_task_bar = False
    p.window.minimized = False
    return p


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_settings_path",
                         lambda: tmp_path / "settings.json")


def test_hide_to_tray_minimizes_and_skips_taskbar(mock_page):
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm.hide_to_tray()
    assert mock_page.window.skip_task_bar is True
    assert mock_page.window.minimized is True
    mock_page.window.update.assert_called()


def test_hide_to_tray_is_idempotent(mock_page):
    """Second call short-circuits — prevents recursion when minimize event
    re-routes through on_window_event after a programmatic minimize."""
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm.hide_to_tray()
    mock_page.window.update.reset_mock()
    wm.hide_to_tray()
    mock_page.window.update.assert_not_called()


def test_show_from_tray_unminimizes_and_brings_to_front(mock_page):
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    mock_page.window.minimized = True
    mock_page.window.skip_task_bar = True
    wm.show_from_tray()
    assert mock_page.window.minimized is False
    assert mock_page.window.skip_task_bar is False
    # to_front() is async in Flet 0.85; we schedule it via page.run_task.
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


def test_handle_close_action_hide_hides_without_dialog(mock_page):
    settings.set_value(settings.KEY_CLOSE_ACTION, "hide")
    wm = window_manager.WindowManager(mock_page, on_real_quit=MagicMock())
    wm._handle_close()
    assert mock_page.window.minimized is True
    assert mock_page.window.skip_task_bar is True


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
    assert mock_page.window.minimized is True
    assert mock_page.window.skip_task_bar is True


def test_on_window_event_close_routes_to_handle_close(mock_page):
    settings.set_value(settings.KEY_CLOSE_ACTION, "exit")
    cleanup = MagicMock()
    wm = window_manager.WindowManager(mock_page, on_real_quit=cleanup)
    evt = MagicMock(); evt.data = "close"
    wm.on_window_event(evt)
    cleanup.assert_called_once()
