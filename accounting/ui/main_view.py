"""Top-level view: left sidebar (project list) + right card (cross-project stats).

Adds a top search bar that performs a cross-project invoice search and shows
results in place of the stats card. Clicking a result navigates into that
project with the in-project search field pre-filled to the file name (so the
project view's table filters to that single row immediately).
"""
from typing import Callable
import flet as ft

from accounting.services import invoice_service as ivs
from accounting.ui.state import AppState
from accounting.ui.widgets.amount_text import format_amount
from accounting.ui.widgets.status_chip import status_chip


def build_main_view(page: ft.Page, state: AppState,
                    on_open_project: Callable[[int], None],
                    on_new_project: Callable[[], None],
                    on_delete_project: Callable[[int], None],
                    on_open_settings: Callable[[], None],
                    on_open_invoice_in_project: Callable[[int, str], None]
                    ) -> ft.Control:
    """Build the main view.

    on_open_invoice_in_project(project_id, file_name) — navigate to the project
    AND set state.search_query to file_name (so the in-project table filters
    down to that one row).
    """
    sidebar = _build_sidebar(state, on_open_project, on_new_project,
                             on_delete_project)
    settings_btn = ft.IconButton(
        icon=ft.Icons.SETTINGS, tooltip="设置",
        on_click=lambda _e: on_open_settings(),
    )

    # Search field + results-or-stats container that updates IN PLACE
    # (no full re-render, so the search field doesn't lose focus while typing).
    search_field = ft.TextField(
        hint_text="全局搜索: 发票号 / 销售方 / 备注 / 淘宝单号 / 文件名",
        prefix_icon=ft.Icons.SEARCH,
        dense=True, expand=True,
    )

    right_pane = ft.Container(expand=True)

    def _render_right_pane():
        q = (search_field.value or "").strip()
        if not q:
            right_pane.content = _build_stats_card(state)
        else:
            matches = ivs.search_invoices(state.conn, q)
            right_pane.content = _build_results_list(
                state, matches, on_open_invoice_in_project)
        right_pane.update()

    search_field.on_change = lambda _e: _render_right_pane()

    # Initial render: stats card
    right_pane.content = _build_stats_card(state)

    top_bar = ft.Row([
        ft.Container(
            content=search_field, expand=True,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        ),
        settings_btn,
    ])
    body = ft.Row(
        [sidebar, ft.VerticalDivider(width=1), right_pane],
        expand=True,
    )
    return ft.Column([top_bar, body], expand=True)


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


def _build_results_list(state: AppState, matches,
                        on_open_invoice_in_project) -> ft.Control:
    """Render cross-project search results.

    Each row shows: project name chip + filename + (invoice_no, date, seller,
    amount) subtitle + status chip. Clicking navigates into the project with
    the in-project search pre-filled to the file name.
    """
    if not matches:
        return ft.Container(
            content=ft.Text("无匹配结果", color=ft.Colors.OUTLINE),
            padding=20, alignment=ft.Alignment.CENTER,
        )

    project_map = {p.id: p.name for p in state.projects}
    items = []
    for inv in matches:
        proj_name = project_map.get(inv.project_id, "?")
        proj_chip = ft.Container(
            content=ft.Text(proj_name, size=10, color="white", no_wrap=True),
            bgcolor=ft.Colors.BLUE_400,
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=10,
        )
        subtitle_text = (
            f"{inv.invoice_no or '—'}  |  {inv.invoice_date or '—'}  |  "
            f"{inv.seller or '—'}  |  {format_amount(inv.amount)}"
        )

        # Capture the per-row inv via default-arg trick to avoid late-binding
        # (without it every handler would close over the loop's final inv).
        def make_click(invoice):
            return lambda _e: on_open_invoice_in_project(
                invoice.project_id, invoice.file_name)

        items.append(ft.ListTile(
            leading=proj_chip,
            title=ft.Text(inv.file_name, size=13, no_wrap=True,
                          overflow=ft.TextOverflow.ELLIPSIS),
            subtitle=ft.Text(subtitle_text, size=11, color=ft.Colors.OUTLINE),
            trailing=status_chip(inv.status),
            dense=True,
            on_click=make_click(inv),
        ))

    return ft.Container(
        content=ft.Column([
            ft.Text(f"找到 {len(matches)} 个发票",
                    size=12, color=ft.Colors.OUTLINE),
            ft.Divider(height=1),
            ft.ListView(controls=items, expand=True, spacing=2),
        ]),
        padding=10, expand=True,
    )
