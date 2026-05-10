"""Modal dialogs for project create / delete confirmation."""
from typing import Callable
import flet as ft


def show_new_project_dialog(page: ft.Page,
                             on_confirm: Callable[[str], None]) -> None:
    name_field = ft.TextField(label="项目名", autofocus=True)
    error_text = ft.Text("", color=ft.Colors.RED, size=12)

    def on_ok(_e):
        if not name_field.value or not name_field.value.strip():
            error_text.value = "项目名不能为空"
            page.update()
            return
        try:
            on_confirm(name_field.value.strip())
            page.pop_dialog()
        except Exception as ex:
            error_text.value = f"创建失败: {ex}"
            page.update()

    dialog = ft.AlertDialog(
        title=ft.Text("新建项目"),
        content=ft.Column([
            name_field,
            ft.Text("项目文件夹会自动在 %APPDATA%\\rename-invoice\\projects\\ 下创建",
                    size=11, color=ft.Colors.OUTLINE),
            error_text,
        ], tight=True, height=130, width=400),
        actions=[
            ft.TextButton("取消", on_click=lambda _e: page.pop_dialog()),
            ft.ElevatedButton("创建", on_click=on_ok),
        ],
    )
    page.show_dialog(dialog)
