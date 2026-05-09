# Account Manager M1 — Data + Service Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data + service layer for the account-manager app: SQLite schema, dataclass models, project + invoice CRUD services, PDF metadata import. Full pytest coverage. **No UI in M1** — M1 must be testable on its own.

**Architecture:** sqlite3 standard library + hand-written SQL (no ORM). Services accept a `conn` parameter (testable, no global state). Models are plain dataclasses with `from_row` classmethods. PDF metadata extraction reuses `rename_invoice.extract_invoice_metadata` via a thin wrapper.

**Tech Stack:** Python 3.10+, sqlite3, dataclasses, pytest 7+

**Files created in M1:**
- `accounting/__init__.py`
- `accounting/__main__.py`
- `accounting/db.py`
- `accounting/models.py`
- `accounting/extractor.py`
- `accounting/services/__init__.py`
- `accounting/services/project_service.py`
- `accounting/services/invoice_service.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_db.py`
- `tests/test_models.py`
- `tests/test_project_service.py`
- `tests/test_invoice_service.py`
- `tests/test_extractor.py`
- `tests/test_smoke.py`
- `requirements-dev.txt`

---

### Task 1: Project structure + pytest setup

**Files:**
- Create: `accounting/__init__.py`
- Create: `accounting/services/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create directory layout**

```bash
mkdir -p accounting/services accounting/ui tests
```

Create empty files:
- `accounting/__init__.py`
- `accounting/services/__init__.py`
- `tests/__init__.py`

- [ ] **Step 2: Create requirements-dev.txt and install pytest**

Create `requirements-dev.txt`:
```
pytest>=7.0.0
```

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 3: Create conftest.py with shared fixtures**

Create `tests/conftest.py`:
```python
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
```

- [ ] **Step 4: Verify pytest discovers tests**

Run: `pytest tests/ -v`
Expected: `no tests ran in 0.0X s` (no test files yet, no error)

- [ ] **Step 5: Commit**

```bash
git add accounting tests requirements-dev.txt
git commit -m "feat(accounting): scaffold package + pytest fixtures"
```

---

### Task 2: db.py — schema initialization

**Files:**
- Create: `accounting/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_db.py`:
```python
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
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'accounting.db'`

- [ ] **Step 3: Implement db.py**

Create `accounting/db.py`:
```python
"""SQLite schema management for the account-manager app."""
import os
import sqlite3
from pathlib import Path


SCHEMA_VERSION = 1


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
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    """Create schema if not present; record version. Idempotent."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version(version) VALUES (?)",
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_db.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/db.py tests/test_db.py
git commit -m "feat(accounting): SQLite schema + version tracking"
```

---

### Task 3: models.py — Project / Invoice dataclasses

**Files:**
- Create: `accounting/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_models.py`:
```python
from accounting.models import Project, Invoice, VALID_STATUS


def test_valid_status_constants():
    assert "未报销" in VALID_STATUS
    assert "报销中" in VALID_STATUS
    assert "已报销" in VALID_STATUS


def test_project_minimal():
    p = Project(id=None, name="11月报销", folder_path="C:/p")
    assert p.status == "未报销"
    assert p.note is None


def test_invoice_minimal():
    inv = Invoice(id=None, project_id=1, file_name="x.pdf")
    assert inv.status == "未报销"
    assert inv.amount is None
    assert inv.remark is None


def test_project_from_row():
    row = {
        "id": 1, "name": "test", "folder_path": "C:/p",
        "status": "报销中", "note": "n",
        "created_at": "2026-05-09 10:00:00",
        "updated_at": "2026-05-09 10:00:00",
    }
    p = Project.from_row(row)
    assert p.name == "test"
    assert p.status == "报销中"


def test_invoice_from_row():
    row = {
        "id": 1, "project_id": 1, "file_name": "x.pdf",
        "invoice_no": "25...", "invoice_date": "2025年11月18日",
        "invoice_date_iso": "2025-11-18", "seller": "S",
        "amount": 16.6, "remark": None, "taobao_order": None,
        "status": "未报销",
        "created_at": "2026-05-09 10:00:00",
        "updated_at": "2026-05-09 10:00:00",
    }
    inv = Invoice.from_row(row)
    assert inv.amount == 16.6
    assert inv.invoice_date_iso == "2025-11-18"
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement models.py**

Create `accounting/models.py`:
```python
"""Plain dataclass models. created_at / updated_at remain ISO strings (sqlite TEXT)."""
from dataclasses import dataclass
from typing import Any, Mapping, Optional


VALID_STATUS = ("未报销", "报销中", "已报销")


@dataclass
class Project:
    id: Optional[int]
    name: str
    folder_path: str
    status: str = "未报销"
    note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Project":
        return cls(
            id=row["id"],
            name=row["name"],
            folder_path=row["folder_path"],
            status=row["status"],
            note=row["note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Invoice:
    id: Optional[int]
    project_id: int
    file_name: str
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_date_iso: Optional[str] = None
    seller: Optional[str] = None
    amount: Optional[float] = None
    remark: Optional[str] = None
    taobao_order: Optional[str] = None
    status: str = "未报销"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Invoice":
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            file_name=row["file_name"],
            invoice_no=row["invoice_no"],
            invoice_date=row["invoice_date"],
            invoice_date_iso=row["invoice_date_iso"],
            seller=row["seller"],
            amount=row["amount"],
            remark=row["remark"],
            taobao_order=row["taobao_order"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_models.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/models.py tests/test_models.py
git commit -m "feat(accounting): Project / Invoice dataclasses with from_row"
```

---

### Task 4: project_service — create + read

**Files:**
- Create: `accounting/services/project_service.py`
- Create: `tests/test_project_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_project_service.py`:
```python
import pytest
from accounting.services import project_service as ps


def test_create_project_returns_with_id(conn):
    p = ps.create_project(conn, name="11月报销", folder_path="C:/p1")
    assert p.id is not None
    assert p.name == "11月报销"
    assert p.status == "未报销"


def test_create_project_duplicate_folder_raises(conn):
    ps.create_project(conn, name="A", folder_path="C:/dup")
    with pytest.raises(Exception):
        ps.create_project(conn, name="B", folder_path="C:/dup")


def test_get_project_by_id(conn):
    p = ps.create_project(conn, name="x", folder_path="C:/x")
    got = ps.get_project(conn, p.id)
    assert got is not None
    assert got.name == "x"


def test_get_project_missing_returns_none(conn):
    assert ps.get_project(conn, 9999) is None


def test_list_projects(conn):
    ps.create_project(conn, name="A", folder_path="C:/a")
    ps.create_project(conn, name="B", folder_path="C:/b")
    items = ps.list_projects(conn)
    assert len(items) == 2
    assert {p.name for p in items} == {"A", "B"}
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/test_project_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement project_service.py**

Create `accounting/services/project_service.py`:
```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_project_service.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/project_service.py tests/test_project_service.py
git commit -m "feat(accounting): project create/read service"
```

---

### Task 5: project_service — update + delete

**Files:**
- Modify: `accounting/services/project_service.py`
- Modify: `tests/test_project_service.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_project_service.py`:
```python
def test_update_project_status(conn):
    p = ps.create_project(conn, name="x", folder_path="C:/x")
    ps.update_project_status(conn, p.id, "报销中")
    assert ps.get_project(conn, p.id).status == "报销中"


def test_update_project_status_invalid_raises(conn):
    p = ps.create_project(conn, name="x", folder_path="C:/x2")
    with pytest.raises(ValueError):
        ps.update_project_status(conn, p.id, "胡说")


def test_update_project_name_and_note(conn):
    p = ps.create_project(conn, name="old", folder_path="C:/u")
    ps.update_project(conn, p.id, name="new", note="hello")
    got = ps.get_project(conn, p.id)
    assert got.name == "new"
    assert got.note == "hello"


def test_update_project_no_args_is_noop(conn):
    p = ps.create_project(conn, name="o", folder_path="C:/n")
    ps.update_project(conn, p.id)  # no fields, must not raise
    assert ps.get_project(conn, p.id).name == "o"


def test_delete_project(conn):
    p = ps.create_project(conn, name="d", folder_path="C:/d")
    ps.delete_project(conn, p.id)
    assert ps.get_project(conn, p.id) is None
```

- [ ] **Step 2: Run to confirm fails**

Run: `pytest tests/test_project_service.py -v -k "update or delete"`
Expected: FAILs (`AttributeError: module ... has no attribute 'update_project_status'`)

- [ ] **Step 3: Append to project_service.py**

Append to `accounting/services/project_service.py`:
```python
from accounting.models import VALID_STATUS


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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_project_service.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/project_service.py tests/test_project_service.py
git commit -m "feat(accounting): project update/delete + status flow"
```

---

### Task 6: invoice_service — create + read

**Files:**
- Create: `accounting/services/invoice_service.py`
- Create: `tests/test_invoice_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_invoice_service.py`:
```python
import pytest
from accounting.services import project_service as ps
from accounting.services import invoice_service as ivs


@pytest.fixture
def project(conn):
    return ps.create_project(conn, name="P", folder_path="C:/proj")


def test_create_invoice(conn, project):
    inv = ivs.create_invoice(
        conn, project_id=project.id, file_name="a.pdf",
        invoice_no="2595", invoice_date="2025年11月18日",
        invoice_date_iso="2025-11-18", seller="S", amount=16.60,
    )
    assert inv.id is not None
    assert inv.amount == 16.60
    assert inv.status == "未报销"


def test_create_invoice_duplicate_file_raises(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    with pytest.raises(Exception):
        ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")


def test_create_invoice_same_filename_diff_project(conn):
    p1 = ps.create_project(conn, name="P1", folder_path="C:/1")
    p2 = ps.create_project(conn, name="P2", folder_path="C:/2")
    ivs.create_invoice(conn, project_id=p1.id, file_name="a.pdf")
    ivs.create_invoice(conn, project_id=p2.id, file_name="a.pdf")  # ok, scoped


def test_list_invoices_in_project(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.create_invoice(conn, project_id=project.id, file_name="b.pdf")
    items = ivs.list_invoices(conn, project.id)
    assert len(items) == 2


def test_get_invoice(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="x.pdf")
    got = ivs.get_invoice(conn, inv.id)
    assert got.file_name == "x.pdf"


def test_get_invoice_missing(conn):
    assert ivs.get_invoice(conn, 9999) is None
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/test_invoice_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement invoice_service.py**

Create `accounting/services/invoice_service.py`:
```python
"""Invoice CRUD."""
import sqlite3
from typing import List, Optional

from accounting.models import Invoice


def create_invoice(conn: sqlite3.Connection, project_id: int, file_name: str,
                   invoice_no: Optional[str] = None,
                   invoice_date: Optional[str] = None,
                   invoice_date_iso: Optional[str] = None,
                   seller: Optional[str] = None,
                   amount: Optional[float] = None,
                   remark: Optional[str] = None,
                   taobao_order: Optional[str] = None,
                   status: str = "未报销") -> Invoice:
    cur = conn.execute(
        """
        INSERT INTO invoice(project_id, file_name, invoice_no, invoice_date,
                            invoice_date_iso, seller, amount, remark,
                            taobao_order, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, file_name, invoice_no, invoice_date, invoice_date_iso,
         seller, amount, remark, taobao_order, status),
    )
    conn.commit()
    return get_invoice(conn, cur.lastrowid)


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> Optional[Invoice]:
    row = conn.execute(
        "SELECT * FROM invoice WHERE id = ?", (invoice_id,)
    ).fetchone()
    return Invoice.from_row(row) if row else None


def list_invoices(conn: sqlite3.Connection, project_id: int) -> List[Invoice]:
    rows = conn.execute(
        """
        SELECT * FROM invoice WHERE project_id = ?
        ORDER BY invoice_date_iso DESC, id DESC
        """,
        (project_id,),
    ).fetchall()
    return [Invoice.from_row(r) for r in rows]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_invoice_service.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/invoice_service.py tests/test_invoice_service.py
git commit -m "feat(accounting): invoice create/read service"
```

---

### Task 7: invoice_service — update field + status + delete

**Files:**
- Modify: `accounting/services/invoice_service.py`
- Modify: `tests/test_invoice_service.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_invoice_service.py`:
```python
def test_update_invoice_field(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.update_invoice_field(conn, inv.id, "remark", "hello")
    assert ivs.get_invoice(conn, inv.id).remark == "hello"


def test_update_invoice_field_invalid_column_raises(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    with pytest.raises(ValueError):
        ivs.update_invoice_field(conn, inv.id, "DROP TABLE invoice", "x")


def test_update_invoice_status(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.update_invoice_status(conn, inv.id, "已报销")
    assert ivs.get_invoice(conn, inv.id).status == "已报销"


def test_update_invoice_status_invalid_raises(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    with pytest.raises(ValueError):
        ivs.update_invoice_status(conn, inv.id, "胡说")


def test_delete_invoice(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.delete_invoice(conn, inv.id)
    assert ivs.get_invoice(conn, inv.id) is None


def test_delete_project_cascades_invoices(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.create_invoice(conn, project_id=project.id, file_name="b.pdf")
    ps.delete_project(conn, project.id)
    assert ivs.list_invoices(conn, project.id) == []
```

- [ ] **Step 2: Run to confirm fails**

Run: `pytest tests/test_invoice_service.py -v -k "update or delete"`
Expected: FAILs (functions undefined)

- [ ] **Step 3: Append to invoice_service.py**

Append to `accounting/services/invoice_service.py`:
```python
from accounting.models import VALID_STATUS


# 仅允许编辑这几列, 防 SQL 注入 (column 名从 UI 来)
EDITABLE_COLUMNS = (
    "invoice_no", "invoice_date", "invoice_date_iso",
    "seller", "amount", "remark", "taobao_order",
)


def update_invoice_field(conn: sqlite3.Connection, invoice_id: int,
                         column: str, value) -> None:
    if column not in EDITABLE_COLUMNS:
        raise ValueError(f"Column not editable: {column!r}")
    conn.execute(
        f"UPDATE invoice SET {column} = ?, updated_at = CURRENT_TIMESTAMP "
        f"WHERE id = ?",
        (value, invoice_id),
    )
    conn.commit()


def update_invoice_status(conn: sqlite3.Connection, invoice_id: int,
                          status: str) -> None:
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status!r}")
    conn.execute(
        "UPDATE invoice SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, invoice_id),
    )
    conn.commit()


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    conn.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
    conn.commit()
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_invoice_service.py -v`
Expected: 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/invoice_service.py tests/test_invoice_service.py
git commit -m "feat(accounting): invoice update/delete + status flow"
```

---

### Task 8: invoice_service — fuzzy search

**Files:**
- Modify: `accounting/services/invoice_service.py`
- Modify: `tests/test_invoice_service.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_invoice_service.py`:
```python
def test_search_by_invoice_no(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf",
                       invoice_no="25957000000146502141")
    ivs.create_invoice(conn, project_id=project.id, file_name="b.pdf",
                       invoice_no="25322000000545152811")
    found = ivs.search_invoices(conn, "25957")
    assert len(found) == 1
    assert found[0].invoice_no.startswith("25957")


def test_search_by_seller(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf",
                       seller="深圳市立创")
    ivs.create_invoice(conn, project_id=project.id, file_name="b.pdf",
                       seller="苏州卡方")
    found = ivs.search_invoices(conn, "立创")
    assert len(found) == 1


def test_search_by_remark(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf",
                       remark="差旅项目-A")
    found = ivs.search_invoices(conn, "差旅")
    assert len(found) == 1


def test_search_scoped_to_project(conn):
    p1 = ps.create_project(conn, name="P1", folder_path="C:/sa")
    p2 = ps.create_project(conn, name="P2", folder_path="C:/sb")
    ivs.create_invoice(conn, project_id=p1.id, file_name="x.pdf",
                       seller="苏州")
    ivs.create_invoice(conn, project_id=p2.id, file_name="y.pdf",
                       seller="苏州")
    found = ivs.search_invoices(conn, "苏州", project_id=p1.id)
    assert len(found) == 1
    assert found[0].project_id == p1.id


def test_search_no_match(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf",
                       seller="X")
    assert ivs.search_invoices(conn, "不存在") == []
```

- [ ] **Step 2: Run to confirm fails**

Run: `pytest tests/test_invoice_service.py -v -k search`
Expected: FAILs (`search_invoices` undefined)

- [ ] **Step 3: Append search to invoice_service.py**

Append to `accounting/services/invoice_service.py`:
```python
def search_invoices(conn: sqlite3.Connection, query: str,
                    project_id: Optional[int] = None) -> List[Invoice]:
    """模糊匹配 invoice_no / seller / remark / taobao_order / file_name."""
    pattern = f"%{query}%"
    sql = """
        SELECT * FROM invoice
        WHERE (invoice_no LIKE ? OR seller LIKE ? OR remark LIKE ?
               OR taobao_order LIKE ? OR file_name LIKE ?)
    """
    args: list = [pattern] * 5
    if project_id is not None:
        sql += " AND project_id = ?"
        args.append(project_id)
    sql += " ORDER BY invoice_date_iso DESC, id DESC"
    rows = conn.execute(sql, tuple(args)).fetchall()
    return [Invoice.from_row(r) for r in rows]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_invoice_service.py -v`
Expected: 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/invoice_service.py tests/test_invoice_service.py
git commit -m "feat(accounting): invoice fuzzy search across fields"
```

---

### Task 9: invoice_service — status aggregations

**Files:**
- Modify: `accounting/services/invoice_service.py`
- Modify: `tests/test_invoice_service.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_invoice_service.py`:
```python
def test_stats_by_invoice_status(conn, project):
    ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf",
                       amount=10.0, status="已报销")
    ivs.create_invoice(conn, project_id=project.id, file_name="b.pdf",
                       amount=20.0, status="已报销")
    ivs.create_invoice(conn, project_id=project.id, file_name="c.pdf",
                       amount=15.0, status="报销中")
    stats = ivs.stats_by_invoice_status(conn)
    assert stats["已报销"]["count"] == 2
    assert stats["已报销"]["sum"] == 30.0
    assert stats["报销中"]["count"] == 1
    assert stats["未报销"]["count"] == 0
    assert stats["未报销"]["sum"] == 0.0


def test_stats_by_invoice_status_scoped(conn):
    p1 = ps.create_project(conn, name="P1", folder_path="C:/sp1")
    p2 = ps.create_project(conn, name="P2", folder_path="C:/sp2")
    ivs.create_invoice(conn, project_id=p1.id, file_name="a.pdf",
                       amount=10.0, status="已报销")
    ivs.create_invoice(conn, project_id=p2.id, file_name="b.pdf",
                       amount=99.0, status="已报销")
    stats = ivs.stats_by_invoice_status(conn, project_id=p1.id)
    assert stats["已报销"]["sum"] == 10.0


def test_stats_by_project_status(conn):
    p1 = ps.create_project(conn, name="P1", folder_path="C:/p1",
                           status="已报销")
    p2 = ps.create_project(conn, name="P2", folder_path="C:/p2",
                           status="未报销")
    ivs.create_invoice(conn, project_id=p1.id, file_name="x.pdf", amount=100.0)
    ivs.create_invoice(conn, project_id=p2.id, file_name="y.pdf", amount=50.0)
    stats = ivs.stats_by_project_status(conn)
    assert stats["已报销"]["count"] == 1
    assert stats["已报销"]["sum"] == 100.0
    assert stats["未报销"]["count"] == 1
    assert stats["未报销"]["sum"] == 50.0
```

- [ ] **Step 2: Run to confirm fails**

Run: `pytest tests/test_invoice_service.py -v -k stats`
Expected: FAILs

- [ ] **Step 3: Append stats to invoice_service.py**

Append to `accounting/services/invoice_service.py`:
```python
def stats_by_invoice_status(conn: sqlite3.Connection,
                            project_id: Optional[int] = None) -> dict:
    """{status: {count, sum}}; 三个 status 都有 (无数据时 0)."""
    out = {s: {"count": 0, "sum": 0.0} for s in VALID_STATUS}
    sql = "SELECT status, COUNT(*) c, COALESCE(SUM(amount), 0) s FROM invoice"
    args: tuple = ()
    if project_id is not None:
        sql += " WHERE project_id = ?"
        args = (project_id,)
    sql += " GROUP BY status"
    for row in conn.execute(sql, args):
        out[row["status"]] = {"count": row["c"], "sum": float(row["s"])}
    return out


def stats_by_project_status(conn: sqlite3.Connection) -> dict:
    """{project.status: {count: 项目数, sum: 项目下发票总金额}}."""
    out = {s: {"count": 0, "sum": 0.0} for s in VALID_STATUS}
    sql = """
        SELECT p.status,
               COUNT(DISTINCT p.id) c,
               COALESCE(SUM(i.amount), 0) s
        FROM project p
        LEFT JOIN invoice i ON i.project_id = p.id
        GROUP BY p.status
    """
    for row in conn.execute(sql):
        out[row["status"]] = {"count": row["c"], "sum": float(row["s"])}
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_invoice_service.py -v`
Expected: 20 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/invoice_service.py tests/test_invoice_service.py
git commit -m "feat(accounting): status aggregation queries (invoice + project)"
```

---

### Task 10: extractor.py — wraps rename_invoice + ISO date helper

**Files:**
- Create: `accounting/extractor.py`
- Create: `tests/test_extractor.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing test**

Create `tests/test_extractor.py`:
```python
"""Verify extractor wraps rename_invoice + normalizes Chinese date."""
from pathlib import Path
import pytest
from accounting import extractor


SAMPLE_DIR = Path(__file__).parent / "_pdf_samples"


def test_chinese_date_to_iso():
    assert extractor.chinese_date_to_iso("2025年11月18日") == "2025-11-18"
    assert extractor.chinese_date_to_iso("2025年1月3日") == "2025-01-03"


def test_chinese_date_to_iso_none_or_garbage():
    assert extractor.chinese_date_to_iso(None) is None
    assert extractor.chinese_date_to_iso("") is None
    assert extractor.chinese_date_to_iso("乱码无日期") is None


def test_chinese_date_to_iso_embedded():
    """日期可能嵌在更长文本里, 应能提取."""
    assert extractor.chinese_date_to_iso("开票日期: 2025年11月18日") == "2025-11-18"


@pytest.mark.skipif(
    not SAMPLE_DIR.exists() or not list(SAMPLE_DIR.glob("*.pdf")),
    reason="no PDF samples in tests/_pdf_samples (gitignored). Drop a PDF in to run.",
)
def test_extract_returns_dict_with_keys():
    pdf = next(SAMPLE_DIR.glob("*.pdf"))
    meta = extractor.extract(pdf)
    assert "amount" in meta
    assert "invoice_no" in meta
    assert "date" in meta
    assert "seller" in meta
    assert "invoice_date_iso" in meta
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/test_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement extractor.py**

Create `accounting/extractor.py`:
```python
"""Wrap rename_invoice.extract_invoice_metadata + add ISO date for storage."""
import re
import sys
from pathlib import Path
from typing import Optional

# rename_invoice.py 在 repo 根, 不是 package - 把 repo 根加进 sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import rename_invoice  # noqa: E402


_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def chinese_date_to_iso(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def extract(pdf_path: Path) -> dict:
    """
    返回 dict, 多一个 invoice_date_iso (派生自 date) 用于 sqlite 排序/索引.
    rename_invoice 原来的字段 (amount/amount_reason/invoice_no/date/seller) 全保留.
    """
    meta = rename_invoice.extract_invoice_metadata(Path(pdf_path))
    meta["invoice_date_iso"] = chinese_date_to_iso(meta.get("date"))
    return meta
```

- [ ] **Step 4: Add gitignore for sample PDFs**

Append to `.gitignore` (open the file and add at the bottom):
```
# 单元测试用的脱敏 PDF 样本, 本地放, 不入库
tests/_pdf_samples/
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_extractor.py -v`
Expected: 3 PASS, 1 SKIPPED (the optional PDF integration test)

- [ ] **Step 6: (optional) verify with a real PDF**

```bash
mkdir -p tests/_pdf_samples
# Copy any one of your existing invoice PDFs
cp "C:/Users/liuyu/Desktop/WorkPlace/报销/test/某发票.pdf" tests/_pdf_samples/
pytest tests/test_extractor.py -v
```
Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add accounting/extractor.py tests/test_extractor.py .gitignore
git commit -m "feat(accounting): extractor wrapper + chinese-date-to-iso helper"
```

---

### Task 11: invoice_service — import_pdf

**Files:**
- Modify: `accounting/services/invoice_service.py`
- Modify: `tests/test_invoice_service.py`

- [ ] **Step 1: Append failing tests (mock extractor)**

Append to `tests/test_invoice_service.py`:
```python
from unittest.mock import patch
from pathlib import Path


def test_import_pdf_creates_invoice(conn, project, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"fake")
    fake_meta = {
        "amount": "16.60", "amount_reason": None,
        "invoice_no": "25957", "date": "2025年11月18日",
        "invoice_date_iso": "2025-11-18", "seller": "深圳市立创",
    }
    with patch("accounting.services.invoice_service.extractor.extract",
               return_value=fake_meta):
        inv = ivs.import_pdf(conn, project.id, pdf)
    assert inv.invoice_no == "25957"
    assert inv.invoice_date_iso == "2025-11-18"
    assert inv.seller == "深圳市立创"
    assert inv.amount == 16.60
    assert inv.file_name == "test.pdf"


def test_import_pdf_no_amount_still_creates(conn, project, tmp_path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"x")
    fake_meta = {
        "amount": None, "amount_reason": "未找到中文大写金额",
        "invoice_no": None, "date": None,
        "invoice_date_iso": None, "seller": None,
    }
    with patch("accounting.services.invoice_service.extractor.extract",
               return_value=fake_meta):
        inv = ivs.import_pdf(conn, project.id, pdf)
    assert inv.amount is None
    assert inv.invoice_no is None


def test_import_pdf_duplicate_filename_raises(conn, project, tmp_path):
    pdf = tmp_path / "same.pdf"
    pdf.write_bytes(b"x")
    fake_meta = {
        "amount": None, "amount_reason": None,
        "invoice_no": None, "date": None,
        "invoice_date_iso": None, "seller": None,
    }
    with patch("accounting.services.invoice_service.extractor.extract",
               return_value=fake_meta):
        ivs.import_pdf(conn, project.id, pdf)
        with pytest.raises(Exception):
            ivs.import_pdf(conn, project.id, pdf)
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/test_invoice_service.py -v -k import_pdf`
Expected: FAIL (`import_pdf` undefined)

- [ ] **Step 3: Update invoice_service.py imports + add import_pdf**

At the top of `accounting/services/invoice_service.py`, add (after existing imports):
```python
from pathlib import Path
from accounting import extractor
```

Append to `accounting/services/invoice_service.py`:
```python
def import_pdf(conn: sqlite3.Connection, project_id: int,
               pdf_path: Path) -> Invoice:
    """读 PDF -> 提字段 -> INSERT invoice 行. amount 为 None 时仍会插入."""
    meta = extractor.extract(Path(pdf_path))
    amt: Optional[float] = None
    if meta.get("amount"):
        try:
            amt = float(meta["amount"])
        except (TypeError, ValueError):
            amt = None
    return create_invoice(
        conn,
        project_id=project_id,
        file_name=Path(pdf_path).name,
        invoice_no=meta.get("invoice_no"),
        invoice_date=meta.get("date"),
        invoice_date_iso=meta.get("invoice_date_iso"),
        seller=meta.get("seller"),
        amount=amt,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_invoice_service.py -v`
Expected: 23 tests PASS

- [ ] **Step 5: Commit**

```bash
git add accounting/services/invoice_service.py tests/test_invoice_service.py
git commit -m "feat(accounting): import_pdf — extract metadata + insert invoice"
```

---

### Task 12: __main__.py + end-to-end smoke test

**Files:**
- Create: `accounting/__main__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write smoke test**

Create `tests/test_smoke.py`:
```python
"""End-to-end smoke covering: schema -> project -> invoice -> search -> stats."""
from accounting import db
from accounting.services import project_service as ps
from accounting.services import invoice_service as ivs


def test_full_flow(temp_db_path):
    db.init_schema(str(temp_db_path))
    conn = db.connect(str(temp_db_path))
    try:
        p = ps.create_project(conn, name="11月报销", folder_path="C:/n11")
        ivs.create_invoice(conn, project_id=p.id, file_name="a.pdf",
                           invoice_no="2595", seller="A", amount=100.0,
                           status="已报销")
        ivs.create_invoice(conn, project_id=p.id, file_name="b.pdf",
                           invoice_no="2532", seller="B", amount=50.0,
                           status="未报销")

        assert len(ivs.list_invoices(conn, p.id)) == 2

        # search
        found = ivs.search_invoices(conn, "B")
        assert len(found) == 1
        assert found[0].seller == "B"

        # stats
        st = ivs.stats_by_invoice_status(conn)
        assert st["已报销"]["sum"] == 100.0
        assert st["未报销"]["sum"] == 50.0

        # status flow
        ivs.update_invoice_status(conn, found[0].id, "报销中")
        st = ivs.stats_by_invoice_status(conn)
        assert st["报销中"]["count"] == 1
        assert st["未报销"]["count"] == 0
    finally:
        conn.close()
```

- [ ] **Step 2: Implement __main__.py**

Create `accounting/__main__.py`:
```python
"""Bootstrap: ensure schema exists. UI comes in M2."""
from accounting import db


def main():
    path = db.default_db_path()
    db.init_schema(str(path))
    print(f"[OK] schema initialized at {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run smoke + verify __main__**

Run:
```bash
pytest tests/test_smoke.py -v
python -m accounting
```
Expected:
- smoke: PASS
- __main__: prints `[OK] schema initialized at C:\Users\<you>\AppData\Roaming\rename-invoice\accounts.db`

- [ ] **Step 4: Run the full test suite as final gate**

Run: `pytest tests/ -v`
Expected: ~24 tests PASS, 1 SKIPPED (PDF samples, optional)

- [ ] **Step 5: Commit**

```bash
git add accounting/__main__.py tests/test_smoke.py
git commit -m "feat(accounting): __main__ bootstrap + e2e smoke test"
```

---

## M1 Done — Definition of Done

- ✅ `pytest tests/ -v` → all PASS (PDF samples test may SKIP, that's OK)
- ✅ `python -m accounting` → creates `%APPDATA%\rename-invoice\accounts.db`, prints OK
- ✅ git log shows ~12 incremental commits (one per task)
- ✅ No UI code yet (`accounting/ui/` directory exists but empty/placeholder)

After M1 ships as a PR to `feat/account-manager`, start M2 (Flet UI).
