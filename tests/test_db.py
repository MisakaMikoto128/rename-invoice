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
