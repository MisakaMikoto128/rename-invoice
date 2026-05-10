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
