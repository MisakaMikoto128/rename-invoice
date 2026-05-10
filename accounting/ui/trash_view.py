"""Trash view: list trashed projects with restore / permanent delete."""
from typing import Callable
import flet as ft

from accounting.services import project_service as ps
from accounting.ui.state import AppState


def build_trash_view(state: AppState, on_back: Callable[[], None],
                     on_changed: Callable[[], None],
                     show_confirm: Callable[..., None]) -> ft.Control:
    """Trash list. show_confirm(title, message, on_confirm) — passthrough to
    a configured dialogs.show_confirm_dialog.
    """
    items = []
    for p in ps.list_trashed_projects(state.conn):
        deleted_at = p.deleted_at or ""

        def make_restore(pid):
            def go(_e):
                ps.restore_project(state.conn, pid)
                on_changed()
            return go

        def make_purge(pid, name):
            def go(_e):
                show_confirm(
                    title="永久删除",
                    message=(f"永久删除 \"{name}\"? "
                             f"数据库记录会彻底清空（含发票）。"
                             f"PDF 文件保留在原文件夹里。"),
                    on_confirm=lambda: (
                        ps.delete_project(state.conn, pid),
                        on_changed(),
                    ),
                )
            return go

        items.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.DELETE_FOREVER,
                            color=ft.Colors.GREY_500),
            title=ft.Text(p.name),
            subtitle=ft.Text(f"删除于 {deleted_at}", size=11,
                             color=ft.Colors.OUTLINE),
            trailing=ft.Row([
                ft.TextButton("恢复", icon=ft.Icons.RESTORE,
                              on_click=make_restore(p.id)),
                ft.TextButton("永久删除", icon=ft.Icons.DELETE_FOREVER,
                              on_click=make_purge(p.id, p.name)),
            ], tight=True),
        ))

    if not items:
        body = ft.Container(
            content=ft.Text("回收站为空", color=ft.Colors.OUTLINE),
            padding=40, alignment=ft.Alignment.CENTER,
        )
    else:
        body = ft.ListView(controls=items, expand=True, spacing=2)

    header = ft.Row([
        ft.IconButton(icon=ft.Icons.ARROW_BACK,
                      on_click=lambda _e: on_back()),
        ft.Text("回收站", size=20, weight=ft.FontWeight.BOLD),
    ])

    return ft.Column([
        ft.Container(content=header, padding=10),
        ft.Divider(height=1),
        body,
    ], expand=True)
