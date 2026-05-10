import sqlite3
from accounting import db


def test_init_schema_creates_tables(temp_db_path):
    db.init_schema(str(temp_db_path))
    c = sqlite3.connect(str(temp_db_path))
    tables = {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    c.close()
    assert "project" in tables
    assert "invoice" in tables
    assert "schema_version" in tables


def test_init_schema_idempotent(temp_db_path):
    db.init_schema(str(temp_db_path))
    db.init_schema(str(temp_db_path))  # second call must not raise


def test_init_schema_records_version(temp_db_path):
    db.init_schema(str(temp_db_path))
    c = sqlite3.connect(str(temp_db_path))
    row = c.execute("SELECT version FROM schema_version").fetchone()
    c.close()
    assert row[0] == db.SCHEMA_VERSION


def test_connect_enables_foreign_keys(temp_db_path):
    db.init_schema(str(temp_db_path))
    conn = db.connect(str(temp_db_path))
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.close()
    assert fk == 1


def test_init_schema_fresh_install_has_deleted_at(temp_db_path):
    """Fresh DB has deleted_at column from the start (v2 schema)."""
    db.init_schema(str(temp_db_path))
    conn = sqlite3.connect(str(temp_db_path))
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(project)").fetchall()}
    conn.close()
    assert "deleted_at" in cols


def test_migration_v1_to_v2_adds_deleted_at(tmp_path):
    """Pre-existing v1 DB (no deleted_at column) gets the column on init."""
    db_path = str(tmp_path / "v1.db")
    # Build a v1 DB by hand (no deleted_at)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version VALUES (1);
        CREATE TABLE project (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            folder_path TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT '未报销',
            note TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO project(name, folder_path) VALUES ('OldProj', 'C:/old');
    """)
    conn.commit()
    conn.close()

    # Run init_schema → migration
    db.init_schema(db_path)

    # Column added
    conn = sqlite3.connect(db_path)
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(project)").fetchall()}
    assert "deleted_at" in cols
    # Version bumped
    v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert v == 2
    # Pre-existing project still there with NULL deleted_at
    row = conn.execute(
        "SELECT name, deleted_at FROM project").fetchone()
    assert row[0] == "OldProj"
    assert row[1] is None
    conn.close()
