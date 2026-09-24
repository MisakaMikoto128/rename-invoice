"""Project folder layout. All projects live under a single storage root.

Migrating the storage root in the future = update default_storage_root() (or
read from a config file). Keeping this in one place means projects' folder_path
in the DB stays valid as long as the root resolution is consistent.
"""
import re
import shutil
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
    """Compute a unique folder path under current_projects_dir() for a project name.

    Side effect: creates current_projects_dir() if missing (but NOT the project folder
    itself — the caller does that, typically by passing this path to create_project +
    later import_pdf with copy_to which mkdirs as needed).
    """
    base = current_projects_dir()
    base.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_folder_name(name)
    candidate = base / sanitized
    n = 2
    while candidate.exists():
        candidate = base / f"{sanitized} ({n})"
        n += 1
    return candidate


def current_projects_dir() -> Path:
    """Active projects root: settings.json 'projects_root' if set, else default."""
    from accounting import settings
    raw = settings.get("projects_root")
    if raw:
        return Path(raw)
    return default_projects_dir()


def migrate_projects_root(conn, new_root) -> dict:
    """Move every project's folder to new_root/<basename>; update DB; persist setting.

    Returns:
      {
        'moved':   [(name, old_path, new_path), ...],
        'skipped': [(name, reason), ...],
        'errors':  [(name, error_message), ...],
        'new_root': str(new_root.resolve()),
      }
    """
    new_root = Path(new_root).resolve()
    new_root.mkdir(parents=True, exist_ok=True)

    rows = conn.execute(
        "SELECT id, name, folder_path FROM project"
    ).fetchall()

    moved, skipped, errors = [], [], []
    for row in rows:
        pid = row["id"]
        name = row["name"]
        old_path = row["folder_path"]
        old = Path(old_path)
        target = new_root / old.name
        try:
            if old.exists() and old.resolve() == target.resolve():
                # already in the right place; just persist setting later
                skipped.append((name, "已在目标位置"))
                continue
            if not old.exists():
                # folder was never created (no PDFs imported) or deleted manually:
                # update DB to point at the new logical location, no FS work.
                conn.execute(
                    "UPDATE project SET folder_path = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (str(target), pid),
                )
                skipped.append((name, "源文件夹不存在; 仅更新 DB 路径"))
                continue
            if target.exists():
                errors.append((name, f"目标已存在: {target}"))
                continue
            shutil.move(str(old), str(target))
            conn.execute(
                "UPDATE project SET folder_path = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(target), pid),
            )
            moved.append((name, str(old), str(target)))
        except Exception as ex:
            errors.append((name, str(ex)))

    conn.commit()
    from accounting import settings
    settings.set_value("projects_root", str(new_root))
    return {
        "moved": moved,
        "skipped": skipped,
        "errors": errors,
        "new_root": str(new_root),
    }
