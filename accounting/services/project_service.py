"""Project CRUD."""
import sqlite3
from typing import List, Optional

from accounting.models import Project, VALID_STATUS


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


def update_project_status(conn: sqlite3.Connection, project_id: int,
                          status: str) -> None:
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status!r}")
    conn.execute(
        "UPDATE project SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, project_id),
    )
    conn.commit()


def update_project(conn: sqlite3.Connection, project_id: int,
                   name: Optional[str] = None,
                   note: Optional[str] = None) -> None:
    sets = []
    args: list = []
    if name is not None:
        sets.append("name = ?")
        args.append(name)
    if note is not None:
        sets.append("note = ?")
        args.append(note)
    if not sets:
        return
    sets.append("updated_at = CURRENT_TIMESTAMP")
    args.append(project_id)
    conn.execute(
        f"UPDATE project SET {', '.join(sets)} WHERE id = ?",
        tuple(args),
    )
    conn.commit()


def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    conn.execute("DELETE FROM project WHERE id = ?", (project_id,))
    conn.commit()


def set_project_status_cascade(conn: sqlite3.Connection, project_id: int,
                               status: str) -> None:
    """Set project status AND cascade the same status to every invoice in the project."""
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status!r}")
    conn.execute(
        "UPDATE project SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, project_id),
    )
    conn.execute(
        "UPDATE invoice SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE project_id = ?",
        (status, project_id),
    )
    conn.commit()
