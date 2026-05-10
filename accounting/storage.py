"""Project folder layout. All projects live under a single storage root.

Migrating the storage root in the future = update default_storage_root() (or
read from a config file). Keeping this in one place means projects' folder_path
in the DB stays valid as long as the root resolution is consistent.
"""
import re
from pathlib import Path

from accounting import db


_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def default_storage_root() -> Path:
    """Single source of truth. %APPDATA%\\rename-invoice on Windows."""
    return Path(db.default_db_path()).parent


def default_projects_dir() -> Path:
    return default_storage_root() / "projects"


def sanitize_folder_name(name: str) -> str:
    """Strip Windows-illegal chars; collapse whitespace; fall back to 'untitled' if empty."""
    cleaned = _INVALID_FILENAME.sub("_", name).strip().rstrip(".")
    return cleaned or "untitled"


def auto_project_folder(name: str) -> Path:
    """Compute a unique folder path under default_projects_dir() for a project name.

    Side effect: creates default_projects_dir() if missing (but NOT the project folder
    itself — the caller does that, typically by passing this path to create_project +
    later import_pdf with copy_to which mkdirs as needed).
    """
    base = default_projects_dir()
    base.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_folder_name(name)
    candidate = base / sanitized
    n = 2
    while candidate.exists():
        candidate = base / f"{sanitized} ({n})"
        n += 1
    return candidate
