"""Top-level view: left sidebar (project list) + right card (cross-project stats)."""
from typing import Callable
import flet as ft

from accounting.services import invoice_service as ivs
from accounting.ui.state import AppState
from accounting.ui.widgets.amount_text import format_amount
from accounting.ui.widgets.status_chip import status_chip


def build_main_view(page: ft.Page, state: AppState,
                    on_open_project: Callable[[int], None],
                    on_new_project: Callable[[], None],
                    on_delete_project: Callable[[int], None]) -> ft.Control:
    sidebar = _build_sidebar(state, on_open_project, on_new_project,
                             on_delete_project)
    stats_card = _build_stats_card(state)
    return ft.Row(
        [sidebar, ft.VerticalDivider(width=1), stats_card],
        expand=True,
    )


def _build_sidebar(state: AppState, on_open_project, on_new_project,
                   on_delete_project) -> ft.Control:
    items = []
    for p in state.projects:
        items.append(
            ft.ListTile(
                title=ft.Text(p.name),
                subtitle=status_chip(p.status),
                on_click=lambda _e, pid=p.id: on_open_project(pid),
                trailing=ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_size=18,
                    tooltip="删除项目",
                    on_click=lambda _e, pid=p.id: on_delete_project(pid),
                ),
            )
        )
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.ElevatedButton(
                    "+ 新建项目", on_click=lambda _e: on_new_project(),
                    expand=True,
                ),
                padding=10,
            ),
            ft.Divider(height=1),
            ft.ListView(controls=items, expand=True, spacing=2)
            if items else ft.Container(
                content=ft.Text("还没有项目, 点上面新建一个", color=ft.Colors.OUTLINE),
                padding=20, alignment=ft.Alignment.CENTER,
            ),
        ]),
        width=280,
    )


def _build_stats_card(state: AppState) -> ft.Control:
    inv_stats = ivs.stats_by_invoice_status(state.conn)
    proj_stats = ivs.stats_by_project_status(state.conn)
    total_amount = sum(s["sum"] for s in inv_stats.values())
    total_count = sum(s["count"] for s in inv_stats.values())

    rows = [
        ft.Row([ft.Text("已报销", size=14), status_chip("已报销"),
                ft.Text(f"{inv_stats['已报销']['count']} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.Text(format_amount(inv_stats['已报销']['sum']), size=16,
                        weight=ft.FontWeight.W_500)]),
        ft.Row([ft.Text("报销中", size=14), status_chip("报销中"),
                ft.Text(f"{inv_stats['报销中']['count']} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.Text(format_amount(inv_stats['报销中']['sum']), size=16,
                        weight=ft.FontWeight.W_500)]),
        ft.Row([ft.Text("未报销", size=14), status_chip("未报销"),
                ft.Text(f"{inv_stats['未报销']['count']} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.Text(format_amount(inv_stats['未报销']['sum']), size=16,
                        weight=ft.FontWeight.W_500)]),
        ft.Divider(),
        ft.Row([ft.Text("总计", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Text(f"{total_count} 张", size=12, color=ft.Colors.OUTLINE),
                ft.Text(format_amount(total_amount), size=18,
                        weight=ft.FontWeight.BOLD)]),
        ft.Container(height=20),
        ft.Text(f"项目: 已报销 {proj_stats['已报销']['count']}, "
                f"报销中 {proj_stats['报销中']['count']}, "
                f"未报销 {proj_stats['未报销']['count']}",
                size=12, color=ft.Colors.OUTLINE),
    ]

    return ft.Container(
        content=ft.Column([
            ft.Text("跨项目统计 (按发票)", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            *rows,
        ]),
        padding=20, expand=True,
    )
