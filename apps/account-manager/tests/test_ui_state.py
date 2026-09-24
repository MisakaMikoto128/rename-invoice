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
