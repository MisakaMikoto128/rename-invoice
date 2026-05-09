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
