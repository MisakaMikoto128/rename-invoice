"""SQLite schema management for the account-manager app."""
import os
import sqlite3
from pathlib import Path


SCHEMA_VERSION = 2


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS project (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    folder_path  TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT '未报销'
                 CHECK(status IN ('未报销','报销中','已报销')),
    note         TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at   TIMESTAMP DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS invoice (
    id               INTEGER PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    file_name        TEXT NOT NULL,
    invoice_no       TEXT,
    invoice_date     TEXT,
    invoice_date_iso TEXT,
    seller           TEXT,
    amount           REAL,
    remark           TEXT,
    taobao_order     TEXT,
    status           TEXT NOT NULL DEFAULT '未报销'
                     CHECK(status IN ('未报销','报销中','已报销')),
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, file_name)
);

CREATE INDEX IF NOT EXISTS idx_invoice_project ON invoice(project_id);
CREATE INDEX IF NOT EXISTS idx_invoice_status  ON invoice(status);
CREATE INDEX IF NOT EXISTS idx_invoice_date    ON invoice(invoice_date_iso);
CREATE INDEX IF NOT EXISTS idx_invoice_seller  ON invoice(seller);
"""


def default_db_path() -> Path:
    """%APPDATA%\\rename-invoice\\accounts.db on Windows; ~/.rename-invoice elsewhere."""
    base = Path(os.environ.get("APPDATA", str(Path.home() / ".local" / "share")))
    return base / "rename-invoice" / "accounts.db"


def init_schema(path: str) -> None:
    """Create schema if not present; record version. Idempotent.

    Migrations:
      v1 -> v2: ADD COLUMN project.deleted_at (soft-delete trash). The
        CREATE TABLE IF NOT EXISTS in SCHEMA_SQL doesn't add columns to
        existing tables, so we explicitly ALTER TABLE when the column is
        missing.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        row = conn.execute(
            "SELECT version FROM schema_version LIMIT 1").fetchone()
        current = row[0] if row else 0

        if current < 2:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(project)").fetchall()}
            if "deleted_at" not in cols:
                conn.execute(
                    "ALTER TABLE project ADD COLUMN deleted_at "
                    "TIMESTAMP DEFAULT NULL")

        if row is None:
            conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                         (SCHEMA_VERSION,))
        elif current != SCHEMA_VERSION:
            conn.execute("UPDATE schema_version SET version = ?",
                         (SCHEMA_VERSION,))
        conn.commit()
    finally:
        conn.close()


def connect(path: str) -> sqlite3.Connection:
    """Open a connection with FK constraints + Row factory."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
