"""Project CRUD."""
import sqlite3
from typing import List, Optional

from accounting.models import Project


def create_project(conn: sqlite3.Connection, name: str, folder_path: str,
                   note: Optional[str] = None,
                   status: str = "未报销") -> Project:
    cur = conn.execute(
        "INSERT INTO project(name, folder_path, note, status) "
        "VALUES (?, ?, ?, ?)",
        (name, folder_path, note, status),
    )
    conn.commit()
    return get_project(conn, cur.lastrowid)


def get_project(conn: sqlite3.Connection, project_id: int) -> Optional[Project]:
    row = conn.execute(
        "SELECT * FROM project WHERE id = ?", (project_id,)
    ).fetchone()
    return Project.from_row(row) if row else None


def list_projects(conn: sqlite3.Connection) -> List[Project]:
    rows = conn.execute(
        "SELECT * FROM project ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [Project.from_row(r) for r in rows]
