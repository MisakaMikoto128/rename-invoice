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
