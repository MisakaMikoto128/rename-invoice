import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# winreg only exists on Windows; tests use a mock and skip on non-Win
if sys.platform != "win32":
    pytest.skip("Windows-only", allow_module_level=True)

from accounting import autostart


@pytest.fixture
def fake_winreg(monkeypatch):
    m = MagicMock()
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
    # SetValueEx(key, value_name, reserved, type, value)
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
    # Should not raise
    autostart.disable()


def test_is_enabled_true_when_value_exists(fake_winreg):
    fake_winreg.QueryValueEx.return_value = (r'"X" --silent', 1)
    assert autostart.is_enabled() is True


def test_is_enabled_false_when_value_missing(fake_winreg):
    fake_winreg.QueryValueEx.side_effect = FileNotFoundError()
    assert autostart.is_enabled() is False
