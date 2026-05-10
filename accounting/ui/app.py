"""Flet entry. Routes between main_view and project_view."""
import flet as ft

from accounting import db, settings
from accounting.ui.main_view import build_main_view
from accounting.ui.project_view import build_project_view
from accounting.ui.state import AppState


def main(page: ft.Page):
    page.title = "rename-invoice / 账目管理"
    page.window.width = 1200
    page.window.height = 720
    saved_theme = settings.get(settings.KEY_THEME_MODE, "light")
    page.theme_mode = (ft.ThemeMode.DARK if saved_theme == "dark"
                       else ft.ThemeMode.LIGHT)
    page.padding = 0

    state = AppState(db_path=str(db.default_db_path()))
    state.init()
    page.on_close = lambda _e: state.close()

    container = ft.Container(expand=True)

    def render_main():
        state.select_project(None)
        state.search_query = ""
        state.status_filter = None

        from accounting.services import project_service as ps_local
        from accounting.ui.dialogs import (
            show_new_project_dialog, show_confirm_dialog,
            show_settings_dialog,
        )
        from accounting import storage as storage_mod

        def new_project():
            def confirm(name):
                ps_local.create_project(state.conn, name=name)  # folder_path auto
                state.refresh_projects()
                render_main()
            show_new_project_dialog(page, confirm)

        def delete_project_action(project_id):
            project = ps_local.get_project(state.conn, project_id)
            name = project.name if project else ""

            def do_trash():
                ps_local.trash_project(state.conn, project_id)
                state.refresh_projects()
                render_main()

                def undo(_e):
                    ps_local.restore_project(state.conn, project_id)
                    state.refresh_projects()
                    render_main()

                page.show_dialog(ft.SnackBar(
                    content=ft.Text(f"项目 \"{name}\" 已移到回收站"),
                    action="撤销",
                    on_action=undo,
                ))

            show_confirm_dialog(
                page,
                title="删除项目",
                message=(f"将 \"{name}\" 移到回收站? "
                         f"项目下所有发票数据会一并标记删除（可恢复）。"
                         f"PDF 文件保留在原文件夹里。"),
                on_confirm=do_trash,
            )

        async def _start_migrate():
            from pathlib import Path as _Path
            file_picker = ft.FilePicker()
            page.services.append(file_picker)
            page.update()
            new_root = await file_picker.get_directory_path(
                dialog_title="选择新的项目根目录")
            if not new_root:
                return
            result = storage_mod.migrate_projects_root(
                state.conn, _Path(new_root))
            parts = [
                f"已迁移 {len(result['moved'])} 个",
                f"跳过 {len(result['skipped'])} 个",
            ]
            if result["errors"]:
                parts.append(f"{len(result['errors'])} 个错误")
            page.show_dialog(ft.SnackBar(
                content=ft.Text("，".join(parts) + f" → {result['new_root']}")))
            state.refresh_projects()
            render_main()

        def open_settings():
            current = str(storage_mod.current_projects_dir())
            count = len(state.projects)

            def trigger_migrate():
                page.run_task(_start_migrate)

            show_settings_dialog(page, current_root=current,
                                  project_count=count,
                                  on_migrate=trigger_migrate)

        def open_invoice_in_project(project_id, file_name):
            # Pre-fill the in-project search filter so the table shows just
            # this row. render_project does NOT reset state.search_query, so
            # setting it before the call is picked up by build_project_view.
            state.search_query = file_name
            render_project(project_id)

        container.content = build_main_view(
            page, state,
            on_open_project=lambda pid: render_project(pid),
            on_new_project=new_project,
            on_delete_project=delete_project_action,
            on_open_settings=open_settings,
            on_open_invoice_in_project=open_invoice_in_project,
            on_open_trash=render_trash,
        )
        page.update()

    def render_project(project_id):
        state.refresh_projects()
        state.select_project(project_id)

        def reload():
            render_project(project_id)

        container.content = build_project_view(
            page, state, on_back=render_main, on_changed=reload,
        )
        page.update()

    def render_trash():
        state.refresh_projects()
        from accounting.ui.trash_view import build_trash_view
        from accounting.ui.dialogs import show_confirm_dialog as _confirm

        def confirm_helper(title, message, on_confirm):
            _confirm(page, title=title, message=message,
                     on_confirm=on_confirm)

        container.content = build_trash_view(
            state, on_back=render_main,
            on_changed=lambda: render_trash(),
            show_confirm=confirm_helper,
        )
        page.update()

    page.add(container)
    render_main()


if __name__ == "__main__":
    ft.run(main)
