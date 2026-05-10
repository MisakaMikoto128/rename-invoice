"""Project detail view: header (back/import/export/status) + two-pane (PDF list / table)."""
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Callable
import flet as ft

from accounting import settings
from accounting.models import VALID_STATUS
from accounting.services import project_service as ps
from accounting.services import invoice_service as ivs
from accounting.ui.state import AppState
from accounting.ui.widgets.status_chip import status_chip
from accounting.ui.widgets.editable_cell import EditableTextCell
from accounting.ui.widgets.amount_text import format_amount


def _build_zip(target_path: str, invoices: list, project_folder: Path,
               include_xlsx: bool) -> None:
    """Bundle PDFs (and optionally an xlsx summary) into a zip at target_path.

    Missing source files are skipped silently (e.g. file renamed/deleted on
    disk after import). When include_xlsx is True, a temp xlsx is generated
    via rename_invoice.write_summary_xlsx and embedded as 发票汇总.xlsx.
    """
    target = Path(target_path)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            src = project_folder / inv.file_name
            if src.exists():
                zf.write(src, arcname=inv.file_name)
        if include_xlsx:
            from rename_invoice import write_summary_xlsx
            tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            tmp.close()
            try:
                rows = [
                    {
                        "filename": inv.file_name,
                        "invoice_no": inv.invoice_no,
                        "date": inv.invoice_date,
                        "seller": inv.seller,
                        "amount": inv.amount,
                    }
                    for inv in invoices
                ]
                write_summary_xlsx(rows, Path(tmp.name))
                zf.write(tmp.name, arcname="发票汇总.xlsx")
            finally:
                Path(tmp.name).unlink(missing_ok=True)


def build_project_view(page: ft.Page, state: AppState,
                       on_back: Callable[[], None],
                       on_changed: Callable[[], None]) -> ft.Control:
    p = state.current_project
    if p is None:
        return ft.Text("(no project selected)")

    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    page.update()

    # Lift invoice fetch + total here so closures below can reference `invoices`
    # via late-binding (handlers fire after this returns, so `invoices` is bound).
    if state.search_query:
        invoices = ivs.search_invoices(state.conn, state.search_query,
                                       project_id=p.id)
    else:
        invoices = ivs.list_invoices(state.conn, p.id)
    total = sum(inv.amount or 0 for inv in invoices)

    def _total_prefix():
        # Recompute lazily from current `invoices` list — `apply_filter` may
        # rebind `invoices` when search query changes. Empty list → no prefix.
        t = sum(inv.amount or 0 for inv in invoices)
        return f"{t:.2f}元-" if invoices else ""

    async def on_pick_click(_e):
        from pathlib import Path as _Path
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
            allow_multiple=True,
            initial_directory=settings.get(settings.KEY_LAST_IMPORT_DIR),
        )
        if not files:
            return
        if files[0].path:
            settings.set_value(settings.KEY_LAST_IMPORT_DIR,
                               os.path.dirname(files[0].path))
        project_dir = _Path(p.folder_path)
        imported = 0
        duplicates = 0
        failed: list[tuple[str, str]] = []
        for f in files:
            if not f.path:
                continue
            try:
                result = ivs.import_pdf(state.conn, p.id, _Path(f.path),
                                        copy_to=project_dir)
                if result is None:
                    duplicates += 1
                else:
                    imported += 1
            except Exception as ex:
                failed.append((f.name, str(ex)))
        parts = [f"导入 {imported}"]
        if duplicates:
            parts.append(f"跳过 {duplicates} 重复")
        if failed:
            parts.append(f"{len(failed)} 失败")
        msg = "，".join(parts)
        if failed:
            msg += " — " + "; ".join(f"{n}: {e}" for n, e in failed)
        page.show_dialog(ft.SnackBar(content=ft.Text(msg)))
        on_changed()

    async def on_export_xlsx_click(_e):
        from pathlib import Path as _Path
        save_path = await file_picker.save_file(
            dialog_title="导出 xlsx",
            file_name=f"{_total_prefix()}{p.name}_发票汇总.xlsx",
            allowed_extensions=["xlsx"],
            file_type=ft.FilePickerFileType.CUSTOM,
            initial_directory=settings.get(settings.KEY_LAST_EXPORT_XLSX_DIR),
        )
        if not save_path:
            return
        settings.set_value(settings.KEY_LAST_EXPORT_XLSX_DIR,
                           os.path.dirname(save_path))
        try:
            from rename_invoice import write_summary_xlsx
            rows = [
                {
                    "filename": inv.file_name,
                    "invoice_no": inv.invoice_no,
                    "date": inv.invoice_date,
                    "seller": inv.seller,
                    "amount": inv.amount,
                }
                for inv in invoices
            ]
            write_summary_xlsx(rows, _Path(save_path))
            page.show_dialog(ft.SnackBar(
                content=ft.Text(f"已导出 xlsx: {save_path}")))
        except Exception as ex:
            page.show_dialog(ft.SnackBar(
                content=ft.Text(f"导出失败: {ex}")))

    def on_export_zip_click(_e):
        # Step 1: small modal asking for filename + checkboxes.
        # The actual save_file + zip-build runs inside on_ok (async),
        # because page.show_dialog does not block.
        name_input = ft.TextField(
            label="zip 文件名",
            value=f"{_total_prefix()}{p.name}.zip",
            autofocus=True,
        )
        include_prefix = ft.Checkbox(label="附带总价格前缀", value=True)
        include_xlsx = ft.Checkbox(label="同时附带 Excel 汇总 (xlsx)",
                                   value=False)
        error_text = ft.Text("", color=ft.Colors.RED, size=12)

        def regen_name(_e3):
            if include_prefix.value:
                name_input.value = f"{_total_prefix()}{p.name}.zip"
            else:
                name_input.value = f"{p.name}.zip"
            name_input.update()

        include_prefix.on_change = regen_name

        async def on_ok(_e2):
            if not (name_input.value or "").strip():
                error_text.value = "文件名不能为空"
                page.update()
                return
            zip_name = name_input.value.strip()
            want_xlsx = bool(include_xlsx.value)
            page.pop_dialog()
            save_path = await file_picker.save_file(
                dialog_title="保存 zip 到",
                file_name=zip_name,
                allowed_extensions=["zip"],
                file_type=ft.FilePickerFileType.CUSTOM,
                initial_directory=settings.get(settings.KEY_LAST_EXPORT_ZIP_DIR),
            )
            if not save_path:
                return
            settings.set_value(settings.KEY_LAST_EXPORT_ZIP_DIR,
                               os.path.dirname(save_path))
            try:
                _build_zip(save_path, invoices, Path(p.folder_path),
                           include_xlsx=want_xlsx)
                page.show_dialog(ft.SnackBar(
                    content=ft.Text(f"已导出 zip: {save_path}")))
            except Exception as ex:
                page.show_dialog(ft.SnackBar(
                    content=ft.Text(f"导出失败: {ex}")))

        dialog = ft.AlertDialog(
            title=ft.Text("导出 zip"),
            content=ft.Column(
                [name_input, include_prefix, include_xlsx, error_text],
                tight=True, height=200, width=400),
            actions=[
                ft.TextButton("取消", on_click=lambda _e2: page.pop_dialog()),
                ft.ElevatedButton("确认", on_click=on_ok),
            ],
        )
        page.show_dialog(dialog)

    # Define handler before Dropdown construction. In Flet 0.85 the Dropdown
    # event is `on_select` (not `on_change`), and it must be passed via the
    # constructor — assigning it post-hoc on the dataclass is a no-op because
    # the renderer only serializes declared fields.
    def on_status_change(_e):
        ps.set_project_status_cascade(state.conn, p.id, status_dd.value)
        state.refresh_projects()
        on_changed()

    status_dd = ft.Dropdown(
        value=p.status,
        options=[ft.dropdown.Option(s) for s in VALID_STATUS],
        width=120,
        on_select=on_status_change,
    )

    def on_rename_click(_e):
        from accounting.ui.dialogs import show_rename_project_dialog

        def confirm(new_name):
            ps.update_project(state.conn, p.id, name=new_name)
            state.refresh_projects()
            on_changed()

        show_rename_project_dialog(page, p.name, confirm)

    header = ft.Row([
        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _e: on_back()),
        ft.Text(p.name, size=20, weight=ft.FontWeight.BOLD),
        ft.IconButton(icon=ft.Icons.EDIT, tooltip="改项目名",
                      on_click=on_rename_click),
        status_dd,
        ft.Container(expand=True),
        ft.ElevatedButton("+ 导入 PDF", icon=ft.Icons.UPLOAD_FILE,
                          on_click=on_pick_click),
        ft.OutlinedButton("导出 xlsx", icon=ft.Icons.DOWNLOAD,
                          on_click=on_export_xlsx_click),
        ft.OutlinedButton("导出 zip", icon=ft.Icons.FOLDER_ZIP,
                          on_click=on_export_zip_click),
    ])

    search_field = ft.TextField(
        value=state.search_query,
        hint_text="搜索发票号/销售方/备注/淘宝单号/文件名",
        prefix_icon=ft.Icons.SEARCH, dense=True, expand=True,
    )

    def make_status_dd(invoice_id, current):
        # Flet 0.85 Dropdown uses `on_select`, and it must be wired via the
        # constructor (late-assignment is a no-op because the renderer only
        # serializes declared dataclass fields). We read the new value from
        # `e.control.value` since `dd` isn't yet bound when the handler is
        # defined.
        def on_select(e):
            ivs.update_invoice_status(state.conn, invoice_id, e.control.value)
            on_changed()
        dd = ft.Dropdown(
            value=current,
            options=[ft.dropdown.Option(s) for s in VALID_STATUS],
            dense=True, width=110,
            on_select=on_select,
        )
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

    def confirm_delete_invoice(invoice_id, file_name):
        from accounting.ui.dialogs import show_confirm_dialog

        def do_delete():
            ivs.delete_invoice(state.conn, invoice_id)
            on_changed()

        show_confirm_dialog(
            page,
            title="删除发票",
            message=f"确定删除 \"{file_name}\" 的数据库记录? PDF 文件保留。",
            on_confirm=do_delete,
        )

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
                ft.DataCell(ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_size=18,
                    tooltip="删除发票",
                    on_click=lambda _e, iid=inv.id, fname=inv.file_name:
                        confirm_delete_invoice(iid, fname),
                )),
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
            ft.DataColumn(ft.Text("")),
        ],
        rows=build_rows(invoices),
        column_spacing=10,
    )

    total_text = ft.Text(f"合计 (本项目): {format_amount(total)}",
                         weight=ft.FontWeight.BOLD, size=14)
    pdf_count_text = ft.Text(f"PDF ({len(invoices)})", size=14,
                             weight=ft.FontWeight.W_500)

    def open_pdf(invoice):
        pdf_path = Path(p.folder_path) / invoice.file_name
        if not pdf_path.exists():
            page.show_dialog(ft.SnackBar(
                content=ft.Text(f"文件不存在: {pdf_path}")))
            return
        try:
            os.startfile(str(pdf_path))
        except Exception as ex:
            page.show_dialog(ft.SnackBar(
                content=ft.Text(f"打开失败: {ex}")))

    def build_pdf_items(invoices_list):
        items = []
        for inv in invoices_list:
            # default-arg trick (`inv=inv`) avoids late-binding bug — without
            # it every row's handler would close over the loop's final inv.
            items.append(ft.ListTile(
                leading=ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED_400),
                title=ft.Text(inv.file_name, size=12, no_wrap=True,
                              overflow=ft.TextOverflow.ELLIPSIS),
                dense=True,
                on_click=lambda _e, inv=inv: open_pdf(inv),
            ))
        return items

    pdf_list_view = ft.ListView(controls=build_pdf_items(invoices),
                                expand=True, spacing=0)
    pdf_empty_placeholder = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.UPLOAD_FILE,
                    color=ft.Colors.OUTLINE, size=32),
            ft.Text("暂无 PDF",
                    color=ft.Colors.OUTLINE, size=13,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER),
            ft.Text("请点上方「+ 导入 PDF」按钮选择文件\n(当前 Flet 版本暂不支持系统拖放)",
                    color=ft.Colors.OUTLINE, size=11,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.CENTER, spacing=8),
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
        nonlocal invoices
        query = (search_field.value or "").strip()
        state.search_query = query
        if query:
            new_invoices = ivs.search_invoices(state.conn, query,
                                               project_id=p.id)
        else:
            new_invoices = ivs.list_invoices(state.conn, p.id)
        invoices = new_invoices  # rebind so export handlers + _total_prefix see filtered list
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
