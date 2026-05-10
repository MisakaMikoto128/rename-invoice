from pathlib import Path
import pytest
from accounting import storage


def test_sanitize_basic():
    assert storage.sanitize_folder_name("11月报销") == "11月报销"
    assert storage.sanitize_folder_name("a/b") == "a_b"
    assert storage.sanitize_folder_name("a:b*c?") == "a_b_c_"
    assert storage.sanitize_folder_name("  ") == "untitled"
    assert storage.sanitize_folder_name(".") == "untitled"


def test_auto_project_folder_collision(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "default_projects_dir", lambda: tmp_path)
    p1 = storage.auto_project_folder("X")
    assert p1.name == "X"
    p1.mkdir()  # simulate the project folder being created
    p2 = storage.auto_project_folder("X")
    assert p2.name == "X (2)"
    p2.mkdir()
    p3 = storage.auto_project_folder("X")
    assert p3.name == "X (3)"


def test_auto_project_folder_creates_base(tmp_path, monkeypatch):
    base = tmp_path / "newroot" / "projects"
    monkeypatch.setattr(storage, "default_projects_dir", lambda: base)
    storage.auto_project_folder("Y")
    assert base.exists()
