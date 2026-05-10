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


def test_set_project_status_cascade(conn):
    from accounting.services import invoice_service as ivs
    p = ps.create_project(conn, name="P", folder_path="C:/cascade")
    inv1 = ivs.create_invoice(conn, project_id=p.id, file_name="a.pdf",
                              status="未报销")
    inv2 = ivs.create_invoice(conn, project_id=p.id, file_name="b.pdf",
                              status="未报销")
    ps.set_project_status_cascade(conn, p.id, "已报销")
    assert ps.get_project(conn, p.id).status == "已报销"
    assert ivs.get_invoice(conn, inv1.id).status == "已报销"
    assert ivs.get_invoice(conn, inv2.id).status == "已报销"


def test_set_project_status_cascade_invalid_raises(conn):
    p = ps.create_project(conn, name="P", folder_path="C:/cascade2")
    with pytest.raises(ValueError):
        ps.set_project_status_cascade(conn, p.id, "胡说")
