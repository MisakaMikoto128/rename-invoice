import pytest
import sqlite3


@pytest.fixture
def temp_db_path(tmp_path):
    """Path to a fresh sqlite file in a per-test temp dir."""
    return tmp_path / "test_accounts.db"


@pytest.fixture
def conn(temp_db_path):
    """Open a connection to a freshly initialized DB. Auto-closes."""
    from accounting import db
    db.init_schema(str(temp_db_path))
    c = sqlite3.connect(str(temp_db_path))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()
