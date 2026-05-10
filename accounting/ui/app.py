"""Flet entry point. `python -m accounting.ui.app` to launch."""
import flet as ft


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    page.add(ft.Text("Hello, accounting!", size=24))


if __name__ == "__main__":
    ft.app(target=main)
