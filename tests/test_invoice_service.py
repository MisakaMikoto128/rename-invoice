import pytest
from unittest.mock import patch
from pathlib import Path

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
