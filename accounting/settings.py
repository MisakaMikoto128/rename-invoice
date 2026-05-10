"""Persistent app settings as a small JSON file under storage root."""
import json
from pathlib import Path
from typing import Optional

from accounting.storage import default_storage_root


def _settings_path() -> Path:
    return default_storage_root() / "settings.json"


def _load() -> dict:
    p = _settings_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    return _load().get(key, default)


def set_value(key: str, value: Optional[str]) -> None:
    data = _load()
    if value is None:
        data.pop(key, None)
    else:
        data[key] = value
    _save(data)


# Convenience constants for known keys
KEY_LAST_IMPORT_DIR = "last_import_dir"
KEY_LAST_EXPORT_XLSX_DIR = "last_export_xlsx_dir"
KEY_LAST_EXPORT_ZIP_DIR = "last_export_zip_dir"
KEY_LAST_SAVE_AS_DIR = "last_save_as_dir"
