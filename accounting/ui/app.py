"""Flet entry. `python -m accounting.ui.app` launches the GUI."""
import flet as ft

from accounting import db
from accounting.ui.state import AppState


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    page.theme_mode = ft.ThemeMode.LIGHT

    state = AppState(db_path=str(db.default_db_path()))
    state.init()
    page.on_close = lambda _e: state.close()

    # MainView injected in Task 6.
    page.add(ft.Text(
        f"AppState ready. {len(state.projects)} project(s) in DB.",
        size=18,
    ))


if __name__ == "__main__":
    ft.app(target=main)
