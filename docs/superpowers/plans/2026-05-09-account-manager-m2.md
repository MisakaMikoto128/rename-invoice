# Account Manager M2 — Flet UI Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Flet desktop UI on top of M1's data + service layer. Deliver: main window with project list + cross-project stats, project detail view with two-pane (PDF list + editable invoice table), PDF import (drag-drop where supported, file picker fallback), status dropdowns, search.

**Architecture:** Single Flet `ft.app(target=main)` entry. UI composed of three primary views (`main_view`, `project_view`, `stats_view`) under `accounting/ui/`. State held in a module-level `AppState` dataclass (single conn, current project id, list of projects). Mutations go through services from M1.

**Tech Stack:** Flet 0.x, on top of M1's sqlite3 + dataclasses + services.

**M2 Risks (call out, mitigate via spike):**
1. **Flet DataTable inline editing** — Flet's DataTable doesn't have built-in cell editing. Task 2 SPIKE settles whether to (a) hand-roll editable cells via Container + on-click TextField swap, or (b) use a third-party widget (PlutoGrid Flet port? or community package). Output: a decision documented in the spike's commit message.
2. **Native drag-drop** — Flet 0.x desktop drag-drop file support is not mature. Plan B: file picker via `ft.FilePicker` (always works). Drag-drop becomes additive if Task 11 spike confirms feasibility.

**Files created in M2:**
- `accounting/ui/__init__.py`
- `accounting/ui/app.py`
- `accounting/ui/state.py`
- `accounting/ui/main_view.py`
- `accounting/ui/project_view.py`
- `accounting/ui/stats_view.py`
- `accounting/ui/widgets/__init__.py`
- `accounting/ui/widgets/status_chip.py`
- `accounting/ui/widgets/amount_text.py`
- `accounting/ui/widgets/editable_cell.py`
- `tests/test_ui_state.py`
- `tests/test_ui_widgets.py`

**Service additions in M2:**
- `invoice_service.update_invoice_fields(conn, id, **changes)` — batch update (plural form)
- `invoice_service.import_pdf(..., copy=True)` — extend to copy file into project folder

---

### Task 1: Add Flet dependency + minimal hello-world

**Goal:** Verify Flet installs and runs in this Python env.

**Files:**
- Modify: `requirements.txt` (add `flet>=0.21.0`)
- Create: `accounting/ui/__init__.py` (empty)
- Create: `accounting/ui/app.py` (hello-world)

- [ ] **Step 1: Add flet to requirements.txt**

Append to `requirements.txt`:
```
flet>=0.21.0
```

Install: `pip install flet>=0.21.0`

- [ ] **Step 2: Hello-world Flet app**

Create `accounting/ui/__init__.py` (empty file).

Create `accounting/ui/app.py`:
```python
"""Flet entry point. `python -m accounting.ui.app` to launch."""
import flet as ft


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    page.add(ft.Text("Hello, accounting!", size=24))


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 3: Launch and verify**

Run: `python -m accounting.ui.app`
Expected: A window opens titled "rename-invoice / 账目管理" with "Hello, accounting!" text.

Close the window manually.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt accounting/ui/__init__.py accounting/ui/app.py
git commit -m "feat(accounting): Flet hello-world entry point"
```

---

### Task 2: SPIKE — verify inline cell editing pattern

**Goal:** Decide which mechanism powers the editable invoice table. Output: a working PoC + decision documented in the commit message.

**Files:**
- Create: `accounting/ui/widgets/__init__.py` (empty)
- Create: `accounting/ui/widgets/editable_cell.py`
- Modify: `accounting/ui/app.py` (temporarily — to demonstrate the spike)

- [ ] **Step 1: Implement editable_cell.py**

Create `accounting/ui/widgets/editable_cell.py`:
```python
"""Click-to-edit text cell. Click → swap Text for TextField → on submit/blur → save callback."""
from typing import Callable, Optional
import flet as ft


class EditableTextCell(ft.Container):
    """
    Display value as Text. Click swaps in TextField. Enter / lose focus → on_save(new_value).
    Esc → revert without saving.
    """

    def __init__(self, value: Optional[str], on_save: Callable[[str], None],
                 placeholder: str = "—"):
        super().__init__()
        self._value = value or ""
        self._on_save = on_save
        self._placeholder = placeholder
        self._build_view()

    def _build_view(self):
        text = self._value if self._value else self._placeholder
        color = ft.Colors.ON_SURFACE if self._value else ft.Colors.OUTLINE
        self.content = ft.Text(text, color=color)
        self.on_click = self._enter_edit
        self.padding = 6

    def _enter_edit(self, _e):
        self._tf = ft.TextField(
            value=self._value, autofocus=True, dense=True,
            on_submit=self._commit, on_blur=self._commit,
        )
        self.content = self._tf
        self.on_click = None
        self.update()

    def _commit(self, _e):
        new_value = self._tf.value
        if new_value != self._value:
            self._value = new_value
            self._on_save(new_value)
        self._build_view()
        self.update()
```

- [ ] **Step 2: Wire up a 3-cell demo in app.py**

Replace `accounting/ui/app.py` body for the spike (will be discarded in Task 3):
```python
"""SPIKE: prove EditableTextCell works. Will be replaced in Task 3."""
import flet as ft
from accounting.ui.widgets.editable_cell import EditableTextCell


def main(page: ft.Page):
    page.title = "spike: editable cells"
    page.window.width = 600
    page.window.height = 300

    log = ft.Text(value="(saved values appear here)")

    def save(field_name):
        return lambda new_value: setattr(log, "value",
            f"saved {field_name}={new_value!r}") or log.update()

    page.add(
        ft.Column([
            ft.Text("Click any cell to edit. Tab/Enter to save, Esc to cancel.",
                    size=14),
            EditableTextCell("foo", save("a")),
            EditableTextCell("", save("b"), placeholder="(empty)"),
            EditableTextCell("123.45", save("c")),
            log,
        ]),
    )


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 3: Manually verify**

Run: `python -m accounting.ui.app`
Manual checks:
1. Click "foo" → text becomes editable, autofocused.
2. Type "bar", press Enter → text shows "bar", log shows `saved a='bar'`.
3. Click empty cell → can edit; on save log shows.
4. Click "123.45", clear it, blur → log shows `saved c=''`.
5. Click cell, change text, press Esc → no, actually Flet TextField doesn't have Esc-cancel built-in. Document this: **Esc cancellation is NOT implemented** in this iteration. on_blur commits — that's the design. Note in commit message.

Close window.

- [ ] **Step 4: Document decision in commit**

```bash
git add accounting/ui/widgets/__init__.py accounting/ui/widgets/editable_cell.py accounting/ui/app.py
git commit -m "$(cat <<'EOF'
feat(accounting): SPIKE editable cell — hand-rolled wins

DataTable doesn't support inline editing natively. Built EditableTextCell
(Container + on_click → swap to TextField → on_blur/on_submit commit).
Verified manually: click → edit → save propagates via on_save callback.

Esc-cancel deferred (Flet TextField has no on_escape); on_blur commits.
PlutoGrid not investigated — handroll is enough for our 7-column table.
EOF
)"
```

---

### Task 3: AppState + main entry point

**Files:**
- Create: `accounting/ui/state.py`
- Create: `tests/test_ui_state.py`
- Modify: `accounting/ui/app.py` (replace spike with real main + route to MainView placeholder)

- [ ] **Step 1: Write failing test**

Create `tests/test_ui_state.py`:
```python
import pytest
from accounting.ui.state import AppState


def test_state_initial(temp_db_path):
    state = AppState(db_path=str(temp_db_path))
    state.init()
    try:
        assert state.conn is not None
        assert state.current_project_id is None
        assert state.projects == []
    finally:
        state.close()


def test_state_load_projects(temp_db_path, conn):
    # `conn` fixture already initialized schema. Insert via service.
    from accounting.services import project_service as ps
    ps.create_project(conn, name="A", folder_path="C:/a")
    ps.create_project(conn, name="B", folder_path="C:/b")

    state = AppState(db_path=str(temp_db_path))
    state.init()
    try:
        state.refresh_projects()
        assert {p.name for p in state.projects} == {"A", "B"}
    finally:
        state.close()


def test_state_select_project(temp_db_path):
    from accounting.services import project_service as ps
    state = AppState(db_path=str(temp_db_path))
    state.init()
    try:
        p = ps.create_project(state.conn, name="X", folder_path="C:/x")
        state.refresh_projects()
        state.select_project(p.id)
        assert state.current_project_id == p.id
        assert state.current_project.name == "X"
    finally:
        state.close()
```

- [ ] **Step 2: Run, confirm fails**

Run: `pytest tests/test_ui_state.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement state.py**

Create `accounting/ui/state.py`:
```python
"""Module-level app state: single sqlite connection + cached project list + current selection."""
from dataclasses import dataclass, field
from typing import List, Optional

from accounting import db
from accounting.models import Project
from accounting.services import project_service as ps


@dataclass
class AppState:
    db_path: str
    conn: Optional[object] = None  # sqlite3.Connection but typed loosely to avoid stubs
    projects: List[Project] = field(default_factory=list)
    current_project_id: Optional[int] = None

    def init(self) -> None:
        db.init_schema(self.db_path)
        self.conn = db.connect(self.db_path)
        self.refresh_projects()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def refresh_projects(self) -> None:
        self.projects = ps.list_projects(self.conn)

    def select_project(self, project_id: Optional[int]) -> None:
        self.current_project_id = project_id

    @property
    def current_project(self) -> Optional[Project]:
        if self.current_project_id is None:
            return None
        for p in self.projects:
            if p.id == self.current_project_id:
                return p
        return None
```

- [ ] **Step 4: Run, confirm 3 pass**

Run: `pytest tests/test_ui_state.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Replace app.py spike with real wiring**

Overwrite `accounting/ui/app.py`:
```python
"""Flet entry. `python -m accounting.ui.app` launches the GUI."""
import flet as ft

from accounting import db
from accounting.ui.state import AppState


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    page.theme_mode = ft.ThemeMode.LIGHT

    state = AppState(db_path=str(db.default_db_path()))
    state.init()
    page.on_close = lambda _e: state.close()

    # MainView injected in Task 5.
    page.add(ft.Text(
        f"AppState ready. {len(state.projects)} project(s) in DB.",
        size=18,
    ))


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 6: Verify**

Run: `python -m accounting.ui.app`
Expected: window shows e.g. "AppState ready. 0 project(s) in DB." (or N if M1 left some).

- [ ] **Step 7: Commit**

```bash
git add accounting/ui/state.py tests/test_ui_state.py accounting/ui/app.py
git commit -m "feat(accounting): AppState + Flet main wiring"
```

---

### Task 4: Service additions for batch update + PDF copy

**Files:**
- Modify: `accounting/services/invoice_service.py` (append)
- Modify: `tests/test_invoice_service.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_invoice_service.py`:
```python
def test_update_invoice_fields_batch(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.update_invoice_fields(conn, inv.id, remark="hi", taobao_order="T1")
    got = ivs.get_invoice(conn, inv.id)
    assert got.remark == "hi"
    assert got.taobao_order == "T1"


def test_update_invoice_fields_invalid_column_raises(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    with pytest.raises(ValueError):
        ivs.update_invoice_fields(conn, inv.id, status="已报销")  # status is not editable via this path


def test_update_invoice_fields_no_changes_is_noop(conn, project):
    inv = ivs.create_invoice(conn, project_id=project.id, file_name="a.pdf")
    ivs.update_invoice_fields(conn, inv.id)  # no kwargs, no-op
    assert ivs.get_invoice(conn, inv.id).remark is None


def test_import_pdf_with_copy(conn, project, tmp_path):
    src = tmp_path / "src" / "x.pdf"
    src.parent.mkdir()
    src.write_bytes(b"fake pdf")
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    fake_meta = {
        "amount": "16.60", "amount_reason": None,
        "invoice_no": "1", "date": None,
        "invoice_date_iso": None, "seller": "S",
    }
    with patch("accounting.services.invoice_service.extractor.extract",
               return_value=fake_meta):
        inv = ivs.import_pdf(conn, project.id, src,
                             copy_to=project_dir)
    # Original is still in src; a copy is now in project_dir
    assert (project_dir / "x.pdf").exists()
    assert src.exists()
    assert inv.file_name == "x.pdf"


def test_import_pdf_copy_collision_uses_safe_name(conn, project, tmp_path):
    """If destination has a same-name file, a (2)/(3) suffix is added."""
    src = tmp_path / "x.pdf"
    src.write_bytes(b"v2")
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "x.pdf").write_bytes(b"v1")  # pre-existing

    fake_meta = {
        "amount": None, "amount_reason": None, "invoice_no": None,
        "date": None, "invoice_date_iso": None, "seller": None,
    }
    with patch("accounting.services.invoice_service.extractor.extract",
               return_value=fake_meta):
        inv = ivs.import_pdf(conn, project.id, src,
                             copy_to=project_dir)
    assert inv.file_name in ("x (2).pdf",)
    assert (project_dir / "x (2).pdf").exists()
    # Pre-existing not overwritten:
    assert (project_dir / "x.pdf").read_bytes() == b"v1"
```

- [ ] **Step 2: Run to confirm fails**

Run: `pytest tests/test_invoice_service.py -v -k "update_invoice_fields or import_pdf_with_copy or import_pdf_copy_collision"`
Expected: FAILs.

- [ ] **Step 3: Implement update_invoice_fields**

Append to `accounting/services/invoice_service.py`:
```python
import shutil


def update_invoice_fields(conn: sqlite3.Connection, invoice_id: int,
                          **changes) -> None:
    """批量更新可编辑字段; 校验所有 column 在 EDITABLE_COLUMNS 内."""
    if not changes:
        return
    for col in changes:
        if col not in EDITABLE_COLUMNS:
            raise ValueError(f"Column not editable: {col!r}")
    sets = ", ".join(f"{col} = ?" for col in changes) + ", updated_at = CURRENT_TIMESTAMP"
    args = tuple(changes.values()) + (invoice_id,)
    conn.execute(f"UPDATE invoice SET {sets} WHERE id = ?", args)
    conn.commit()
```

- [ ] **Step 4: Extend import_pdf to support copy_to**

Replace existing `import_pdf` in `accounting/services/invoice_service.py` with:
```python
def import_pdf(conn: sqlite3.Connection, project_id: int,
               pdf_path: Path,
               copy_to: Optional[Path] = None) -> Invoice:
    """读 PDF -> 提字段 -> 可选复制到 project 目录 -> INSERT invoice 行."""
    src = Path(pdf_path)
    meta = extractor.extract(src)

    if copy_to is not None:
        dest_dir = Path(copy_to)
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / src.name
        if target.exists():
            stem, suffix = src.stem, src.suffix
            n = 2
            while True:
                candidate = dest_dir / f"{stem} ({n}){suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                n += 1
        shutil.copy2(src, target)
        file_name = target.name
    else:
        file_name = src.name

    amt: Optional[float] = None
    if meta.get("amount"):
        try:
            amt = float(meta["amount"])
        except (TypeError, ValueError):
            amt = None
    return create_invoice(
        conn, project_id=project_id, file_name=file_name,
        invoice_no=meta.get("invoice_no"),
        invoice_date=meta.get("date"),
        invoice_date_iso=meta.get("invoice_date_iso"),
        seller=meta.get("seller"),
        amount=amt,
    )
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_invoice_service.py -v`
Expected: 28 tests PASS (23 from M1 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add accounting/services/invoice_service.py tests/test_invoice_service.py
git commit -m "feat(accounting): batch field update + PDF copy-on-import"
```

---

### Task 5: status_chip and amount_text widgets

**Goal:** Reusable display widgets for the table.

**Files:**
- Create: `accounting/ui/widgets/status_chip.py`
- Create: `accounting/ui/widgets/amount_text.py`
- Create: `tests/test_ui_widgets.py`

- [ ] **Step 1: Write failing tests for color mapping**

Create `tests/test_ui_widgets.py`:
```python
from accounting.ui.widgets.status_chip import status_color
from accounting.ui.widgets.amount_text import format_amount


def test_status_color_known():
    assert status_color("未报销") == "#9E9E9E"
    assert status_color("报销中") == "#1976D2"
    assert status_color("已报销") == "#2E7D32"


def test_status_color_unknown_falls_back():
    assert status_color("胡说") == "#9E9E9E"


def test_format_amount_none():
    assert format_amount(None) == "—"


def test_format_amount_basic():
    assert format_amount(16.6) == "¥16.60"
    assert format_amount(905.34) == "¥905.34"


def test_format_amount_negative():
    assert format_amount(-100.5) == "-¥100.50"
```

- [ ] **Step 2: Run, confirm fails**

Run: `pytest tests/test_ui_widgets.py -v`
Expected: FAILs (modules undefined).

- [ ] **Step 3: Implement amount_text**

Create `accounting/ui/widgets/amount_text.py`:
```python
"""¥X.XX display helper."""
from typing import Optional


def format_amount(amount: Optional[float]) -> str:
    if amount is None:
        return "—"
    if amount < 0:
        return f"-¥{abs(amount):,.2f}"
    return f"¥{amount:,.2f}"
```

- [ ] **Step 4: Implement status_chip**

Create `accounting/ui/widgets/status_chip.py`:
```python
"""Pure helper + Flet badge for status."""
import flet as ft

_COLORS = {
    "未报销": "#9E9E9E",  # gray
    "报销中": "#1976D2",  # blue
    "已报销": "#2E7D32",  # green
}


def status_color(status: str) -> str:
    return _COLORS.get(status, "#9E9E9E")


def status_chip(status: str) -> ft.Container:
    """Pill-shaped status badge."""
    return ft.Container(
        content=ft.Text(status, color="white", size=12, weight=ft.FontWeight.W_500),
        bgcolor=status_color(status),
        padding=ft.padding.symmetric(horizontal=8, vertical=2),
        border_radius=10,
    )
```

- [ ] **Step 5: Run, verify pass**

Run: `pytest tests/test_ui_widgets.py -v`
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add accounting/ui/widgets/status_chip.py accounting/ui/widgets/amount_text.py tests/test_ui_widgets.py
git commit -m "feat(accounting): status chip + amount formatter widgets"
```

---

### Task 6: main_view — sidebar (project list) + right-side stats card

**Files:**
- Create: `accounting/ui/main_view.py`
- Modify: `accounting/ui/app.py` (mount MainView)

- [ ] **Step 1: Implement main_view.py**

Create `accounting/ui/main_view.py`:
```python
"""Top-level view: left sidebar (project list) + right card (cross-project stats)."""
from typing import Callable
import flet as ft

from accounting.services import invoice_service as ivs
from accounting.ui.state import AppState
from accounting.ui.widgets.amount_text import format_amount
from accounting.ui.widgets.status_chip import status_chip


def build_main_view(page: ft.Page, state: AppState,
                    on_open_project: Callable[[int], None],
                    on_new_project: Callable[[], None]) -> ft.Control:
    sidebar = _build_sidebar(state, on_open_project, on_new_project)
    stats_card = _build_stats_card(state)
    return ft.Row(
        [sidebar, ft.VerticalDivider(width=1), stats_card],
        expand=True,
    )


def _build_sidebar(state: AppState, on_open_project, on_new_project) -> ft.Control:
    items = []
    for p in state.projects:
        items.append(
            ft.ListTile(
                title=ft.Text(p.name),
                subtitle=status_chip(p.status),
                on_click=lambda _e, pid=p.id: on_open_project(pid),
            )
        )
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.ElevatedButton(
                    "+ 新建项目", on_click=lambda _e: on_new_project(),
                    expand=True,
                ),
                padding=10,
            ),
            ft.Divider(height=1),
            ft.ListView(controls=items, expand=True, spacing=2)
            if items else ft.Container(
                content=ft.Text("还没有项目, 点上面新建一个", color=ft.Colors.OUTLINE),
                padding=20, alignment=ft.alignment.center,
            ),
        ]),
        width=280,
    )


def _build_stats_card(state: AppState) -> ft.Control:
    inv_stats = ivs.stats_by_invoice_status(state.conn)
    proj_stats = ivs.stats_by_project_status(state.conn)
    total_amount = sum(s["sum"] for s in inv_stats.values())
    total_count = sum(s["count"] for s in inv_stats.values())

    rows = [
        ft.Row([ft.Text("已报销", size=14), status_chip("已报销"),
                ft.Text(f"{inv_stats['已报销']['count']} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.Text(format_amount(inv_stats['已报销']['sum']), size=16,
                        weight=ft.FontWeight.W_500)]),
        ft.Row([ft.Text("报销中", size=14), status_chip("报销中"),
                ft.Text(f"{inv_stats['报销中']['count']} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.Text(format_amount(inv_stats['报销中']['sum']), size=16,
                        weight=ft.FontWeight.W_500)]),
        ft.Row([ft.Text("未报销", size=14), status_chip("未报销"),
                ft.Text(f"{inv_stats['未报销']['count']} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.Text(format_amount(inv_stats['未报销']['sum']), size=16,
                        weight=ft.FontWeight.W_500)]),
        ft.Divider(),
        ft.Row([ft.Text("总计", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Text(f"{total_count} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Text(format_amount(total_amount), size=18,
                        weight=ft.FontWeight.BOLD)]),
        ft.Container(height=20),
        ft.Text(f"项目: 已报销 {proj_stats['已报销']['count']}, "
                f"报销中 {proj_stats['报销中']['count']}, "
                f"未报销 {proj_stats['未报销']['count']}",
                size=12, color=ft.Colors.OUTLINE),
    ]

    return ft.Container(
        content=ft.Column([
            ft.Text("跨项目统计 (按发票)", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            *rows,
        ]),
        padding=20, expand=True,
    )
```

- [ ] **Step 2: Mount in app.py**

Replace `accounting/ui/app.py`:
```python
"""Flet entry. `python -m accounting.ui.app` launches the GUI."""
import flet as ft

from accounting import db
from accounting.ui.main_view import build_main_view
from accounting.ui.state import AppState


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    state = AppState(db_path=str(db.default_db_path()))
    state.init()
    page.on_close = lambda _e: state.close()

    container = ft.Container(expand=True)

    def render():
        container.content = build_main_view(
            page, state,
            on_open_project=lambda pid: print(f"TODO Task 7: open project {pid}"),
            on_new_project=lambda: print("TODO Task 13: new project dialog"),
        )
        page.update()

    page.add(container)
    render()


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 3: Manual smoke**

Run: `python -m accounting.ui.app`
Expected:
- 1200×720 window opens
- Left sidebar shows "+ 新建项目" button (and existing projects if any)
- Right side shows stats card with 3 status rows + total
- Clicking a project prints a TODO line in console (no view change yet)

Close window.

- [ ] **Step 4: Commit**

```bash
git add accounting/ui/main_view.py accounting/ui/app.py
git commit -m "feat(accounting): main view — sidebar + cross-project stats card"
```

---

### Task 7: project_view — header + two-pane layout shell

**Files:**
- Create: `accounting/ui/project_view.py`
- Modify: `accounting/ui/app.py` (route to project_view on open)

- [ ] **Step 1: Implement project_view shell**

Create `accounting/ui/project_view.py`:
```python
"""Project detail view: header (back/import/export/status) + two-pane (PDF list / table)."""
from typing import Callable
import flet as ft

from accounting.models import VALID_STATUS
from accounting.services import project_service as ps
from accounting.ui.state import AppState
from accounting.ui.widgets.status_chip import status_chip


def build_project_view(page: ft.Page, state: AppState,
                       on_back: Callable[[], None]) -> ft.Control:
    p = state.current_project
    if p is None:
        return ft.Text("(no project selected)")

    status_dd = ft.Dropdown(
        value=p.status,
        options=[ft.dropdown.Option(s) for s in VALID_STATUS],
        width=120,
    )

    def on_status_change(_e):
        ps.update_project_status(state.conn, p.id, status_dd.value)
        state.refresh_projects()

    status_dd.on_change = on_status_change

    header = ft.Row([
        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _e: on_back()),
        ft.Text(p.name, size=20, weight=ft.FontWeight.BOLD),
        status_dd,
        ft.Container(expand=True),
        ft.ElevatedButton("+ 导入 PDF", icon=ft.Icons.UPLOAD_FILE,
                          on_click=lambda _e: print("TODO Task 11")),
        ft.OutlinedButton("导出 xlsx", icon=ft.Icons.DOWNLOAD,
                          on_click=lambda _e: print("TODO M3")),
    ])

    pdf_list_pane = ft.Container(
        content=ft.Text("(PDF list - Task 8)"),
        width=280, padding=10, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    table_pane = ft.Container(
        content=ft.Text("(invoice table - Task 9)"),
        expand=True, padding=10,
    )

    return ft.Column([
        header,
        ft.Divider(height=1),
        ft.Row([pdf_list_pane, ft.VerticalDivider(width=1), table_pane],
               expand=True),
    ], expand=True)
```

- [ ] **Step 2: Wire route in app.py**

Replace `accounting/ui/app.py`:
```python
"""Flet entry. Routes between main_view and project_view."""
import flet as ft

from accounting import db
from accounting.ui.main_view import build_main_view
from accounting.ui.project_view import build_project_view
from accounting.ui.state import AppState


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    state = AppState(db_path=str(db.default_db_path()))
    state.init()
    page.on_close = lambda _e: state.close()

    container = ft.Container(expand=True)

    def render_main():
        state.select_project(None)
        container.content = build_main_view(
            page, state,
            on_open_project=lambda pid: render_project(pid),
            on_new_project=lambda: print("TODO Task 13"),
        )
        page.update()

    def render_project(project_id):
        state.refresh_projects()
        state.select_project(project_id)
        container.content = build_project_view(page, state, on_back=render_main)
        page.update()

    page.add(container)
    render_main()


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 3: Manual smoke**

If you have no projects yet, create one for testing:
```bash
python -c "from accounting import db; from accounting.services import project_service as ps; conn = db.connect(str(db.default_db_path())); db.init_schema(str(db.default_db_path())); ps.create_project(conn, name='测试项目', folder_path='C:/temp/test_acc'); print('done')"
```

Run: `python -m accounting.ui.app`
Expected:
- main view with "测试项目" in sidebar
- click → project view with header (back arrow, name, status dropdown, import/export buttons), two-pane stub below
- changing status dropdown → no error (status flows to DB)
- back arrow → returns to main view, sidebar still shows project

- [ ] **Step 4: Commit**

```bash
git add accounting/ui/project_view.py accounting/ui/app.py
git commit -m "feat(accounting): project view shell + main↔project routing"
```

---

### Task 8: PDF list pane (left)

**Files:**
- Modify: `accounting/ui/project_view.py` — replace pdf_list_pane stub

- [ ] **Step 1: Build PDF list ListView**

Replace the `pdf_list_pane` block in `accounting/ui/project_view.py` with:
```python
    from accounting.services import invoice_service as ivs

    invoices = ivs.list_invoices(state.conn, p.id)
    pdf_items = []
    for inv in invoices:
        pdf_items.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED_400),
            title=ft.Text(inv.file_name, size=12, no_wrap=True,
                          overflow=ft.TextOverflow.ELLIPSIS),
            dense=True,
            on_click=lambda _e, iid=inv.id: print(f"TODO highlight row for {iid}"),
        ))

    pdf_list_pane = ft.Container(
        content=ft.Column([
            ft.Text(f"PDF ({len(invoices)})", size=14, weight=ft.FontWeight.W_500),
            ft.Divider(height=1),
            ft.ListView(controls=pdf_items, expand=True, spacing=0)
            if pdf_items else ft.Container(
                content=ft.Text("(空 — 拖入 PDF 或点上方导入)",
                                color=ft.Colors.OUTLINE, size=12),
                padding=20,
            ),
        ]),
        width=280, padding=10, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
```

(The `from accounting.services import invoice_service as ivs` import goes near the top of the file, with the other imports.)

- [ ] **Step 2: Manual smoke**

If no invoices in your test project, fast insert one:
```bash
python -c "from accounting import db; from accounting.services import invoice_service as ivs; conn = db.connect(str(db.default_db_path())); ivs.create_invoice(conn, project_id=1, file_name='dummy.pdf', amount=100.0, seller='X'); print('done')"
```

Run: `python -m accounting.ui.app`, click into the project. Expect to see "PDF (N)" header and at least one ListTile.

- [ ] **Step 3: Commit**

```bash
git add accounting/ui/project_view.py
git commit -m "feat(accounting): PDF list pane (left) in project view"
```

---

### Task 9: Invoice table (right pane) with inline editing

**Files:**
- Modify: `accounting/ui/project_view.py` — replace table_pane stub

- [ ] **Step 1: Build editable DataTable**

Replace the `table_pane` block in `project_view.py` with:
```python
    from accounting.ui.widgets.editable_cell import EditableTextCell
    from accounting.ui.widgets.amount_text import format_amount
    from accounting.models import VALID_STATUS

    def make_status_dd(invoice_id, current):
        dd = ft.Dropdown(
            value=current,
            options=[ft.dropdown.Option(s) for s in VALID_STATUS],
            dense=True, width=110,
        )
        def on_change(_e):
            ivs.update_invoice_status(state.conn, invoice_id, dd.value)
        dd.on_change = on_change
        return dd

    def make_field_cell(invoice_id, column, value):
        def save(new_value):
            ivs.update_invoice_field(state.conn, invoice_id, column,
                                     new_value if new_value else None)
        return EditableTextCell(value, on_save=save)

    def make_amount_cell(invoice_id, value):
        def save(new_value):
            try:
                amt = float(new_value) if new_value else None
            except ValueError:
                amt = value  # revert silently on invalid input
            ivs.update_invoice_field(state.conn, invoice_id, "amount", amt)
        return EditableTextCell(format_amount(value).lstrip("¥"), on_save=save)

    rows = []
    for inv in invoices:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text(inv.file_name, no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=inv.file_name)),
            ft.DataCell(make_field_cell(inv.id, "invoice_no", inv.invoice_no)),
            ft.DataCell(make_field_cell(inv.id, "invoice_date", inv.invoice_date)),
            ft.DataCell(make_field_cell(inv.id, "seller", inv.seller)),
            ft.DataCell(make_field_cell(inv.id, "remark", inv.remark)),
            ft.DataCell(make_field_cell(inv.id, "taobao_order", inv.taobao_order)),
            ft.DataCell(make_amount_cell(inv.id, inv.amount)),
            ft.DataCell(make_status_dd(inv.id, inv.status)),
        ]))

    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("文件")),
            ft.DataColumn(ft.Text("发票号")),
            ft.DataColumn(ft.Text("日期")),
            ft.DataColumn(ft.Text("销售方")),
            ft.DataColumn(ft.Text("备注")),
            ft.DataColumn(ft.Text("淘宝单号")),
            ft.DataColumn(ft.Text("金额"), numeric=True),
            ft.DataColumn(ft.Text("状态")),
        ],
        rows=rows,
        column_spacing=10,
    )

    total = sum(inv.amount or 0 for inv in invoices)
    table_pane = ft.Container(
        content=ft.Column([
            ft.Container(content=table, expand=True),
            ft.Container(
                content=ft.Row([
                    ft.Container(expand=True),
                    ft.Text(f"合计 (本项目): {format_amount(total)}",
                            weight=ft.FontWeight.BOLD, size=14),
                ]),
                padding=10,
            ),
        ]),
        expand=True, padding=10,
    )
```

- [ ] **Step 2: Manual smoke**

Run: `python -m accounting.ui.app`. Click into the test project.
Manual checks:
1. Table shows columns: 文件 / 发票号 / 日期 / 销售方 / 备注 / 淘宝单号 / 金额 / 状态.
2. Click 备注 cell → edit → Tab → value persists. Reload (close + reopen app) — value is in DB.
3. Click 金额 cell → enter "50.0" → blur → cell shows "50.00".
4. Change 状态 dropdown → status saves to DB.
5. 合计 at bottom matches sum of amounts.

- [ ] **Step 3: Commit**

```bash
git add accounting/ui/project_view.py
git commit -m "feat(accounting): editable invoice table in project view"
```

---

### Task 10: Refresh after edits

**Goal:** When a cell is edited or a status changes, the dependent UI (合计, sidebar status, stats card) updates without manual reload.

**Files:**
- Modify: `accounting/ui/project_view.py` — add a `refresh_view()` callable threaded through cell save callbacks
- Modify: `accounting/ui/app.py` — re-render project view on demand

- [ ] **Step 1: Lift view rebuild into a callable**

Modify `accounting/ui/app.py` so `render_project` is captured so cell saves can trigger it. Replace the `render_project` definition:
```python
    def render_project(project_id):
        state.refresh_projects()
        state.select_project(project_id)

        def reload():
            render_project(project_id)

        container.content = build_project_view(
            page, state, on_back=render_main, on_changed=reload,
        )
        page.update()
```

- [ ] **Step 2: Accept on_changed in project_view**

Modify the `build_project_view` signature in `project_view.py`:
```python
def build_project_view(page: ft.Page, state: AppState,
                       on_back: Callable[[], None],
                       on_changed: Callable[[], None]) -> ft.Control:
```

In every save callback (status dropdown changes, EditableTextCell saves, status of invoice), append a call to `on_changed()` after the service write. For example:
```python
    def make_field_cell(invoice_id, column, value):
        def save(new_value):
            ivs.update_invoice_field(state.conn, invoice_id, column,
                                     new_value if new_value else None)
            on_changed()
        return EditableTextCell(value, on_save=save)
```

Apply the same `on_changed()` call in `make_status_dd`, `make_amount_cell`, and the project-status `on_status_change`.

- [ ] **Step 3: Manual smoke**

Run app. In the project view:
1. Edit a 备注 cell → after save, the cell still shows the new value (no flicker).
2. Change a 状态 → 合计 unaffected, but click back → sidebar status chip reflects new value.
3. Change 金额 of one invoice → 合计 updates immediately.

- [ ] **Step 4: Commit**

```bash
git add accounting/ui/project_view.py accounting/ui/app.py
git commit -m "feat(accounting): live refresh after edits"
```

---

### Task 11: Import PDF — file picker + service call

**Files:**
- Modify: `accounting/ui/project_view.py` — replace import button stub with FilePicker

- [ ] **Step 1: Wire FilePicker**

In `project_view.py`, near the top of `build_project_view`, add:
```python
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    page.update()

    def on_pick(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        from pathlib import Path as _Path
        project_dir = _Path(p.folder_path)
        for f in e.files:
            try:
                ivs.import_pdf(state.conn, p.id, _Path(f.path),
                               copy_to=project_dir)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"导入失败: {f.name} — {ex}"))
                page.snack_bar.open = True
                page.update()
        on_changed()

    file_picker.on_result = on_pick
```

Replace the import button:
```python
        ft.ElevatedButton(
            "+ 导入 PDF", icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda _e: file_picker.pick_files(
                allowed_extensions=["pdf"], allow_multiple=True),
        ),
```

- [ ] **Step 2: Manual smoke**

Make sure your test project's folder_path is a real, writable directory:
```bash
python -c "from accounting import db; from accounting.services import project_service as ps; conn = db.connect(str(db.default_db_path())); ps.update_project(conn, 1, name='测试项目'); ps.update_project_status(conn, 1, '未报销'); ps.delete_project(conn, 1)"  # cleanup if needed
mkdir C:\temp\test_acc 2>nul
python -c "from accounting import db; from accounting.services import project_service as ps; conn = db.connect(str(db.default_db_path())); p = ps.create_project(conn, name='M2 测试', folder_path='C:/temp/test_acc'); print(p.id)"
```

Run app, open project. Click "+ 导入 PDF", pick one of the real invoice PDFs from `C:/Users/liuyu/Desktop/WorkPlace/报销/test/`.
Expected:
- File copied into `C:/temp/test_acc/`
- New row in invoice table with extracted fields
- Console shows no errors

- [ ] **Step 3: Commit**

```bash
git add accounting/ui/project_view.py
git commit -m "feat(accounting): import PDF via file picker"
```

---

### Task 12: Search box

**Files:**
- Modify: `accounting/ui/project_view.py` — search box above table; filters rows in-place

- [ ] **Step 1: Add search state + box**

In `build_project_view`, add a search TextField and re-filter on change. After computing `invoices`:
```python
    search_field = ft.TextField(
        hint_text="搜索发票号/销售方/备注/淘宝单号/文件名",
        prefix_icon=ft.Icons.SEARCH, dense=True, expand=True,
    )
    visible_invoices = list(invoices)

    def apply_filter(_e=None):
        nonlocal visible_invoices
        q = (search_field.value or "").strip()
        if q:
            visible_invoices = ivs.search_invoices(state.conn, q,
                                                   project_id=p.id)
        else:
            visible_invoices = list(invoices)
        on_changed()  # re-renders, which re-builds rows from current visible_invoices

    search_field.on_change = apply_filter
```

Then change the row build loop to iterate over `visible_invoices` instead of `invoices`:
```python
    for inv in visible_invoices:
        ...
```

Insert search_field in the column above the two-pane row:
```python
    return ft.Column([
        header,
        ft.Container(content=search_field, padding=10),
        ft.Divider(height=1),
        ft.Row([pdf_list_pane, ft.VerticalDivider(width=1), table_pane],
               expand=True),
    ], expand=True)
```

- [ ] **Step 2: Manual smoke**

Run app, open project with multiple invoices. Type in search box:
- Type 销售方 prefix → table shows only matching rows
- Clear search → all rows back

- [ ] **Step 3: Commit**

```bash
git add accounting/ui/project_view.py
git commit -m "feat(accounting): search box filters invoices in project view"
```

---

### Task 13: New project dialog

**Files:**
- Create: `accounting/ui/dialogs.py`
- Modify: `accounting/ui/app.py` — wire on_new_project

- [ ] **Step 1: Implement dialog helper**

Create `accounting/ui/dialogs.py`:
```python
"""Modal dialogs for project create / delete confirmation."""
from typing import Callable
import flet as ft


def show_new_project_dialog(page: ft.Page,
                             on_confirm: Callable[[str, str], None]) -> None:
    name_field = ft.TextField(label="项目名", autofocus=True)
    folder_field = ft.TextField(label="文件夹路径 (绝对)", hint_text="C:/...")
    error_text = ft.Text("", color=ft.Colors.RED, size=12)

    def on_ok(_e):
        if not name_field.value or not folder_field.value:
            error_text.value = "项目名和文件夹路径都不能为空"
            page.update()
            return
        try:
            on_confirm(name_field.value, folder_field.value)
            page.close(dialog)
        except Exception as ex:
            error_text.value = f"创建失败: {ex}"
            page.update()

    dialog = ft.AlertDialog(
        title=ft.Text("新建项目"),
        content=ft.Column([name_field, folder_field, error_text],
                          tight=True, height=180, width=400),
        actions=[
            ft.TextButton("取消", on_click=lambda _e: page.close(dialog)),
            ft.ElevatedButton("创建", on_click=on_ok),
        ],
    )
    page.open(dialog)
```

- [ ] **Step 2: Wire from app.py**

In `app.py`'s `render_main`, replace the `on_new_project` callback:
```python
        from accounting.services import project_service as ps_
        from accounting.ui.dialogs import show_new_project_dialog

        def new_project():
            def confirm(name, folder):
                ps_.create_project(state.conn, name=name, folder_path=folder)
                state.refresh_projects()
                render_main()
            show_new_project_dialog(page, confirm)

        container.content = build_main_view(
            page, state,
            on_open_project=lambda pid: render_project(pid),
            on_new_project=new_project,
        )
```

- [ ] **Step 3: Manual smoke**

Run app. Click "+ 新建项目". Dialog opens. Type name + folder path, click 创建. Sidebar refreshes with new project. Try creating with empty fields → error message shows. Try duplicate folder_path → error message shows.

- [ ] **Step 4: Commit**

```bash
git add accounting/ui/dialogs.py accounting/ui/app.py
git commit -m "feat(accounting): new project dialog"
```

---

### Task 14: Final manual smoke + README update

**Files:**
- Modify: `README.md` — section "本地账目管理 GUI" with 3-line intro and "python -m accounting.ui.app" instructions

- [ ] **Step 1: Final smoke checklist**

Run `python -m accounting.ui.app` and check all flows:

- [ ] App launches; sidebar + stats card visible
- [ ] "+ 新建项目" creates a project in sidebar; folder path is recorded
- [ ] Click into project → header shows name + status dropdown + import button
- [ ] Status dropdown → updates DB, sidebar reflects on back
- [ ] "+ 导入 PDF" → file picker → selecting a real invoice PDF imports + copies to project folder + appears in table
- [ ] Click 备注 cell → type → save persists across reload
- [ ] Click 金额 cell → type number → format applied
- [ ] Status dropdown in table row → updates 合计 / stats
- [ ] Search box filters table
- [ ] Back arrow returns to main view; stats card refreshed
- [ ] Close window → no traceback

- [ ] **Step 2: README append**

Append to `README.md` under the existing FAQ section:
```markdown
---

## 本地账目管理 GUI (v0.5.0+)

如果你想跨多次报销批次跟踪发票, rename-invoice 还内置一个 Flet 桌面应用:

```bash
pip install -r requirements.txt   # 包含 flet
python -m accounting.ui.app
```

启动后会出现一个 1200×720 的窗口:

- **主窗口**: 左侧项目列表, 右侧跨项目的报销状态统计 (已报销/报销中/未报销 各多少张, 总额)
- **项目详情**: 点项目进入, 上方是 PDF 列表, 下方是可编辑表格 (点单元格直接改备注/淘宝单号/金额等), 右上角状态下拉切换报销状态
- **数据库**: `%APPDATA%\rename-invoice\accounts.db` (SQLite, 单文件备份)

仍支持原有的 CLI 用法; GUI 是可选的.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add account-manager GUI section to README"
```

---

## M2 Done — Definition of Done

- ✅ `pytest tests/ -v` — all green (~55+ tests)
- ✅ `python -m accounting.ui.app` opens and the smoke checklist (Task 14 Step 1) passes
- ✅ ~14 commits on `feat/account-manager`
- ✅ README updated

After M2, M3 adds: stats view standalone page, xlsx export reusing rename_invoice's writer, possibly drag-drop file zone if Flet desktop supports it.
