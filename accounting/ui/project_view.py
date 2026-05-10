"""Project detail view: header (back/import/export/status) + two-pane (PDF list / table)."""
from typing import Callable
import flet as ft

from accounting.models import VALID_STATUS
from accounting.services import project_service as ps
from accounting.services import invoice_service as ivs
from accounting.ui.state import AppState
from accounting.ui.widgets.status_chip import status_chip


def build_project_view(page: ft.Page, state: AppState,
                       on_back: Callable[[], None]) -> ft.Control:
    p = state.current_project
    if p is None:
        return ft.Text("(no project selected)")

    status_dd = ft.Dropdown(
        value=p.status,
        options=[ft.dropdown.Option(s) for s in VALID_STATUS],
        width=120,
    )

    def on_status_change(_e):
        ps.update_project_status(state.conn, p.id, status_dd.value)
        state.refresh_projects()

    status_dd.on_change = on_status_change

    header = ft.Row([
        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _e: on_back()),
        ft.Text(p.name, size=20, weight=ft.FontWeight.BOLD),
        status_dd,
        ft.Container(expand=True),
        ft.ElevatedButton("+ 导入 PDF", icon=ft.Icons.UPLOAD_FILE,
                          on_click=lambda _e: print("TODO Task 11")),
        ft.OutlinedButton("导出 xlsx", icon=ft.Icons.DOWNLOAD,
                          on_click=lambda _e: print("TODO M3")),
    ])

    invoices = ivs.list_invoices(state.conn, p.id)
    pdf_items = []
    for inv in invoices:
        pdf_items.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED_400),
            title=ft.Text(inv.file_name, size=12, no_wrap=True,
                          overflow=ft.TextOverflow.ELLIPSIS),
            dense=True,
            on_click=lambda _e, iid=inv.id: print(f"TODO highlight row for {iid}"),
        ))

    pdf_list_pane = ft.Container(
        content=ft.Column([
            ft.Text(f"PDF ({len(invoices)})", size=14, weight=ft.FontWeight.W_500),
            ft.Divider(height=1),
            ft.ListView(controls=pdf_items, expand=True, spacing=0)
            if pdf_items else ft.Container(
                content=ft.Text("(空 — 拖入 PDF 或点上方导入)",
                                color=ft.Colors.OUTLINE, size=12),
                padding=20,
            ),
        ]),
        width=280, padding=10, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    table_pane = ft.Container(
        content=ft.Text("(invoice table - Task 9)"),
        expand=True, padding=10,
    )

    return ft.Column([
        header,
        ft.Divider(height=1),
        ft.Row([pdf_list_pane, ft.VerticalDivider(width=1), table_pane],
               expand=True),
    ], expand=True)
