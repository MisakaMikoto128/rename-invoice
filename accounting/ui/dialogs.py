"""Modal dialogs for project create / rename / generic delete confirmation."""
from typing import Callable
import flet as ft


def show_confirm_dialog(page: ft.Page, title: str, message: str,
                        on_confirm: Callable[[], object]) -> None:
    """Generic destructive-action confirm dialog.

    Two buttons: 取消 (dismiss) / 删除 (red, runs on_confirm then dismisses).
    """
    def do_confirm(_e):
        page.pop_dialog()
        on_confirm()

    dialog = ft.AlertDialog(
        title=ft.Text(title),
        content=ft.Text(message),
        actions=[
            ft.TextButton("取消", on_click=lambda _e: page.pop_dialog()),
            ft.ElevatedButton("删除", on_click=do_confirm,
                              bgcolor=ft.Colors.RED_400, color="white"),
        ],
    )
    page.show_dialog(dialog)


def show_rename_project_dialog(page: ft.Page, current_name: str,
                                on_confirm: Callable[[str], None]) -> None:
    """Dialog to rename a project. on_confirm receives the new name."""
    name_field = ft.TextField(label="项目名", value=current_name, autofocus=True)
    error_text = ft.Text("", color=ft.Colors.RED, size=12)

    def on_ok(_e):
        new_name = (name_field.value or "").strip()
        if not new_name:
            error_text.value = "项目名不能为空"
            page.update()
            return
        try:
            on_confirm(new_name)
            page.pop_dialog()
        except Exception as ex:
            error_text.value = f"重命名失败: {ex}"
            page.update()

    dialog = ft.AlertDialog(
        title=ft.Text("改项目名"),
        content=ft.Column([
            name_field,
            ft.Text("注意: 项目对应的文件夹名不会改变, 仍是创建时的名字",
                    size=11, color=ft.Colors.OUTLINE),
            error_text,
        ], tight=True, height=130, width=400),
        actions=[
            ft.TextButton("取消", on_click=lambda _e: page.pop_dialog()),
            ft.ElevatedButton("确认", on_click=on_ok),
        ],
    )
    page.show_dialog(dialog)


def show_settings_dialog(page: ft.Page, current_root: str, project_count: int,
                         on_migrate: Callable[[], None]) -> None:
    """Show a settings dialog. on_migrate is called when user clicks 迁移."""
    from accounting import settings as _settings

    current_theme = _settings.get(_settings.KEY_THEME_MODE, "light")
    theme_switch = ft.Switch(label="黑暗模式",
                             value=(current_theme == "dark"))

    def on_theme_change(_e):
        new_theme = "dark" if theme_switch.value else "light"
        _settings.set_value(_settings.KEY_THEME_MODE, new_theme)
        page.theme_mode = (ft.ThemeMode.DARK if new_theme == "dark"
                           else ft.ThemeMode.LIGHT)
        page.update()

    theme_switch.on_change = on_theme_change

    def trigger_migrate(_e):
        page.pop_dialog()
        on_migrate()

    dialog = ft.AlertDialog(
        title=ft.Text("设置"),
        content=ft.Column([
            ft.Text("外观", weight=ft.FontWeight.BOLD),
            theme_switch,
            ft.Container(height=12),
            ft.Text("项目存储根目录", weight=ft.FontWeight.BOLD),
            ft.Text(current_root, size=12, color=ft.Colors.OUTLINE,
                    selectable=True),
            ft.Container(height=8),
            ft.Text(f"{project_count} 个项目", size=12,
                    color=ft.Colors.OUTLINE),
            ft.Container(height=12),
            ft.Text("迁移会把上面这个根目录下的所有项目文件夹整体移到新位置, "
                    "并更新数据库里的路径。数据库本身和设置文件保持在 "
                    "%APPDATA%\\rename-invoice\\ 不变。",
                    size=11, color=ft.Colors.OUTLINE),
        ], tight=True, height=270, width=480),
        actions=[
            ft.TextButton("关闭", on_click=lambda _e: page.pop_dialog()),
            ft.ElevatedButton("迁移到新位置...", icon=ft.Icons.DRIVE_FILE_MOVE,
                              on_click=trigger_migrate),
        ],
    )
    page.show_dialog(dialog)


def show_add_invoice_dialog(page: ft.Page,
                             on_confirm: Callable[[dict], None]) -> None:
    """User fills in invoice fields manually; on_confirm receives a dict.

    Keys in payload: invoice_no, invoice_date (chinese-format string),
    seller, amount (float|None), remark, taobao_order. All values may be None.
    """
    invoice_no = ft.TextField(label="发票号码", autofocus=True)
    date_field = ft.TextField(label="开票日期",
                              hint_text="例: 2026年5月10日 (空白也行)")
    seller = ft.TextField(label="销售方名称")
    amount = ft.TextField(label="金额 (¥)", hint_text="例: 16.60")
    remark = ft.TextField(label="备注名称 (可选)")
    taobao = ft.TextField(label="淘宝单号 (可选)")
    error_text = ft.Text("", color=ft.Colors.RED, size=12)

    def on_ok(_e):
        amt_value = None
        if amount.value and amount.value.strip():
            try:
                amt_value = float(amount.value.strip())
            except ValueError:
                error_text.value = "金额必须是数字"
                page.update()
                return
        payload = {
            "invoice_no": (invoice_no.value or "").strip() or None,
            "invoice_date": (date_field.value or "").strip() or None,
            "seller": (seller.value or "").strip() or None,
            "amount": amt_value,
            "remark": (remark.value or "").strip() or None,
            "taobao_order": (taobao.value or "").strip() or None,
        }
        try:
            on_confirm(payload)
            page.pop_dialog()
        except Exception as ex:
            error_text.value = f"添加失败: {ex}"
            page.update()

    dialog = ft.AlertDialog(
        title=ft.Text("手动添加发票"),
        content=ft.Column([
            invoice_no, date_field, seller, amount, remark, taobao,
            error_text,
        ], tight=True, height=420, width=420, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("取消", on_click=lambda _e: page.pop_dialog()),
            ft.ElevatedButton("添加", on_click=on_ok),
        ],
    )
    page.show_dialog(dialog)


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
