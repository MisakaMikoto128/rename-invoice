"""Project detail view: header (back/import/export/status) + two-pane (PDF list / table)."""
from typing import Callable
import flet as ft

from accounting.models import VALID_STATUS
from accounting.services import project_service as ps
from accounting.services import invoice_service as ivs
from accounting.ui.state import AppState
from accounting.ui.widgets.status_chip import status_chip
from accounting.ui.widgets.editable_cell import EditableTextCell
from accounting.ui.widgets.amount_text import format_amount


def build_project_view(page: ft.Page, state: AppState,
                       on_back: Callable[[], None],
                       on_changed: Callable[[], None]) -> ft.Control:
    p = state.current_project
    if p is None:
        return ft.Text("(no project selected)")

    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    page.update()

    async def on_pick_click(_e):
        from pathlib import Path as _Path
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
            allow_multiple=True,
        )
        if not files:
            return
        project_dir = _Path(p.folder_path)
        for f in files:
            if not f.path:
                continue
            try:
                ivs.import_pdf(state.conn, p.id, _Path(f.path),
                               copy_to=project_dir)
            except Exception as ex:
                page.show_dialog(ft.SnackBar(
                    content=ft.Text(f"导入失败: {f.name} — {ex}")))
                page.update()
        on_changed()

    status_dd = ft.Dropdown(
        value=p.status,
        options=[ft.dropdown.Option(s) for s in VALID_STATUS],
        width=120,
    )

    def on_status_change(_e):
        ps.update_project_status(state.conn, p.id, status_dd.value)
        state.refresh_projects()
        on_changed()

    status_dd.on_change = on_status_change

    header = ft.Row([
        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _e: on_back()),
        ft.Text(p.name, size=20, weight=ft.FontWeight.BOLD),
        status_dd,
        ft.Container(expand=True),
        ft.ElevatedButton("+ 导入 PDF", icon=ft.Icons.UPLOAD_FILE,
                          on_click=on_pick_click),
        ft.OutlinedButton("导出 xlsx", icon=ft.Icons.DOWNLOAD,
                          on_click=lambda _e: print("TODO M3")),
    ])

    if state.search_query:
        invoices = ivs.search_invoices(state.conn, state.search_query,
                                       project_id=p.id)
    else:
        invoices = ivs.list_invoices(state.conn, p.id)

    search_field = ft.TextField(
        value=state.search_query,
        hint_text="搜索发票号/销售方/备注/淘宝单号/文件名",
        prefix_icon=ft.Icons.SEARCH, dense=True, expand=True,
    )

    def make_status_dd(invoice_id, current):
        dd = ft.Dropdown(
            value=current,
            options=[ft.dropdown.Option(s) for s in VALID_STATUS],
            dense=True, width=110,
        )
        def on_change(_e):
            ivs.update_invoice_status(state.conn, invoice_id, dd.value)
            on_changed()
        dd.on_change = on_change
        return dd

    def make_field_cell(invoice_id, column, value):
        def save(new_value):
            ivs.update_invoice_field(state.conn, invoice_id, column,
                                     new_value if new_value else None)
            on_changed()
        return EditableTextCell(value, on_save=save)

    def make_amount_cell(invoice_id, value):
        def save(new_value):
            try:
                amt = float(new_value) if new_value else None
            except ValueError:
                amt = value  # revert silently on invalid input
            ivs.update_invoice_field(state.conn, invoice_id, "amount", amt)
            on_changed()
        display = "" if value is None else f"{value:.2f}"
        return EditableTextCell(display, on_save=save)

    def build_rows(invoices_list):
        rows = []
        for inv in invoices_list:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(inv.file_name, no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    tooltip=inv.file_name)),
                ft.DataCell(make_field_cell(inv.id, "invoice_no", inv.invoice_no)),
                ft.DataCell(make_field_cell(inv.id, "invoice_date", inv.invoice_date)),
                ft.DataCell(make_field_cell(inv.id, "seller", inv.seller)),
                ft.DataCell(make_field_cell(inv.id, "remark", inv.remark)),
                ft.DataCell(make_field_cell(inv.id, "taobao_order", inv.taobao_order)),
                ft.DataCell(make_amount_cell(inv.id, inv.amount)),
                ft.DataCell(make_status_dd(inv.id, inv.status)),
            ]))
        return rows

    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("文件")),
            ft.DataColumn(ft.Text("发票号")),
            ft.DataColumn(ft.Text("日期")),
            ft.DataColumn(ft.Text("销售方")),
            ft.DataColumn(ft.Text("备注")),
            ft.DataColumn(ft.Text("淘宝单号")),
            ft.DataColumn(ft.Text("金额"), numeric=True),
            ft.DataColumn(ft.Text("状态")),
        ],
        rows=build_rows(invoices),
        column_spacing=10,
    )

    total = sum(inv.amount or 0 for inv in invoices)
    total_text = ft.Text(f"合计 (本项目): {format_amount(total)}",
                         weight=ft.FontWeight.BOLD, size=14)
    pdf_count_text = ft.Text(f"PDF ({len(invoices)})", size=14,
                             weight=ft.FontWeight.W_500)

    def build_pdf_items(invoices_list):
        items = []
        for inv in invoices_list:
            items.append(ft.ListTile(
                leading=ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED_400),
                title=ft.Text(inv.file_name, size=12, no_wrap=True,
                              overflow=ft.TextOverflow.ELLIPSIS),
                dense=True,
                on_click=lambda _e, iid=inv.id: print(f"TODO highlight row for {iid}"),
            ))
        return items

    pdf_list_view = ft.ListView(controls=build_pdf_items(invoices),
                                expand=True, spacing=0)
    pdf_empty_placeholder = ft.Container(
        content=ft.Text("(空 — 拖入 PDF 或点上方导入)",
                        color=ft.Colors.OUTLINE, size=12),
        padding=20,
        visible=not invoices,
    )
    pdf_list_view.visible = bool(invoices)

    pdf_list_pane = ft.Container(
        content=ft.Column([
            pdf_count_text,
            ft.Divider(height=1),
            pdf_list_view,
            pdf_empty_placeholder,
        ]),
        width=280, padding=10, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )

    def apply_filter(_e=None):
        query = (search_field.value or "").strip()
        state.search_query = query
        if query:
            new_invoices = ivs.search_invoices(state.conn, query,
                                               project_id=p.id)
        else:
            new_invoices = ivs.list_invoices(state.conn, p.id)
        table.rows = build_rows(new_invoices)
        new_total = sum(inv.amount or 0 for inv in new_invoices)
        total_text.value = f"合计 (本项目): {format_amount(new_total)}"
        pdf_count_text.value = f"PDF ({len(new_invoices)})"
        pdf_list_view.controls = build_pdf_items(new_invoices)
        pdf_list_view.visible = bool(new_invoices)
        pdf_empty_placeholder.visible = not new_invoices
        table.update()
        total_text.update()
        pdf_count_text.update()
        pdf_list_view.update()
        pdf_empty_placeholder.update()

    search_field.on_change = apply_filter

    table_pane = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([table], scroll=ft.ScrollMode.AUTO),
                expand=True,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(expand=True),
                    total_text,
                ]),
                padding=10,
            ),
        ]),
        expand=True, padding=10,
    )

    return ft.Column([
        header,
        ft.Container(content=search_field, padding=10),
        ft.Divider(height=1),
        ft.Row([pdf_list_pane, ft.VerticalDivider(width=1), table_pane],
               expand=True),
    ], expand=True)
