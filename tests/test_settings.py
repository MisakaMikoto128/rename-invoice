import pytest
from accounting import settings


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_settings_path", lambda: tmp_path / "settings.json")


def test_get_missing_returns_default():
    assert settings.get("nope") is None
    assert settings.get("nope", "fallback") == "fallback"


def test_set_then_get():
    settings.set_value("k", "v")
    assert settings.get("k") == "v"


def test_set_persists_across_instances():
    settings.set_value("foo", "bar")
    # Simulate fresh load by hitting _load directly
    assert settings._load()["foo"] == "bar"


def test_set_none_deletes_key():
    settings.set_value("k", "v")
    settings.set_value("k", None)
    assert settings.get("k") is None


def test_set_creates_parent_dir(tmp_path, monkeypatch):
    deeper = tmp_path / "missing" / "settings.json"
    monkeypatch.setattr(settings, "_settings_path", lambda: deeper)
    settings.set_value("k", "v")
    assert deeper.exists()


def test_corrupt_file_returns_empty(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(settings, "_settings_path", lambda: bad)
    assert settings.get("anything") is None
