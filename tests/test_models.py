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
