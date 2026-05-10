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

        def reload():
            render_project(project_id)

        container.content = build_project_view(
            page, state, on_back=render_main, on_changed=reload,
        )
        page.update()

    page.add(container)
    render_main()


if __name__ == "__main__":
    ft.run(main)
