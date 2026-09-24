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


def test_current_projects_dir_falls_back(tmp_path, monkeypatch):
    # Settings file path isolated; setting unset → default fallback
    from accounting import settings
    monkeypatch.setattr(settings, "_settings_path",
                        lambda: tmp_path / "s.json")
    monkeypatch.setattr(storage, "default_projects_dir",
                        lambda: tmp_path / "fallback")
    assert storage.current_projects_dir() == tmp_path / "fallback"


def test_current_projects_dir_uses_setting(tmp_path, monkeypatch):
    from accounting import settings
    monkeypatch.setattr(settings, "_settings_path",
                        lambda: tmp_path / "s.json")
    settings.set_value("projects_root", str(tmp_path / "custom"))
    assert storage.current_projects_dir() == tmp_path / "custom"


def test_migrate_projects_root_moves_folders(tmp_path, monkeypatch, conn):
    """Three projects with real folders → migrate to new root → folders moved + DB updated + setting saved."""
    from accounting import settings
    from accounting.services import project_service as ps
    monkeypatch.setattr(settings, "_settings_path",
                        lambda: tmp_path / "s.json")

    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()

    # Project A: with file
    pa_dir = old_root / "A"
    pa_dir.mkdir()
    (pa_dir / "a.pdf").write_bytes(b"a")
    pa = ps.create_project(conn, name="A", folder_path=str(pa_dir))

    # Project B: empty folder
    pb_dir = old_root / "B"
    pb_dir.mkdir()
    pb = ps.create_project(conn, name="B", folder_path=str(pb_dir))

    # Project C: folder doesn't exist on disk (never imported a PDF)
    pc_path = old_root / "C"
    pc = ps.create_project(conn, name="C", folder_path=str(pc_path))

    result = storage.migrate_projects_root(conn, new_root)

    # Folders A and B physically moved
    assert (new_root / "A" / "a.pdf").exists()
    assert (new_root / "B").exists()
    assert not pa_dir.exists()
    assert not pb_dir.exists()

    # DB updated for all three
    assert ps.get_project(conn, pa.id).folder_path == str((new_root / "A").resolve())
    assert ps.get_project(conn, pb.id).folder_path == str((new_root / "B").resolve())
    assert ps.get_project(conn, pc.id).folder_path == str((new_root / "C").resolve())

    # Setting persisted
    assert settings.get("projects_root") == str(new_root.resolve())

    # Categorized result
    assert len(result["moved"]) == 2
    assert len(result["skipped"]) == 1  # C
    assert len(result["errors"]) == 0


def test_migrate_skips_when_target_exists(tmp_path, monkeypatch, conn):
    from accounting import settings
    from accounting.services import project_service as ps
    monkeypatch.setattr(settings, "_settings_path",
                        lambda: tmp_path / "s.json")

    old_root = tmp_path / "old"; old_root.mkdir()
    new_root = tmp_path / "new"; new_root.mkdir()

    pa_dir = old_root / "A"; pa_dir.mkdir()
    (pa_dir / "x.pdf").write_bytes(b"old")
    pa = ps.create_project(conn, name="A", folder_path=str(pa_dir))

    # pre-existing collision
    (new_root / "A").mkdir()
    (new_root / "A" / "x.pdf").write_bytes(b"new")

    result = storage.migrate_projects_root(conn, new_root)

    assert len(result["errors"]) == 1
    assert "目标已存在" in result["errors"][0][1]
    # original NOT moved, original file intact
    assert (pa_dir / "x.pdf").exists()
    assert (pa_dir / "x.pdf").read_bytes() == b"old"
    # DB still points to old path (not updated on error)
    assert ps.get_project(conn, pa.id).folder_path == str(pa_dir)
