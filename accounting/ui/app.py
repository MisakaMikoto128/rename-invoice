"""SPIKE: prove EditableTextCell works. Will be replaced in Task 3."""
import flet as ft
from accounting.ui.widgets.editable_cell import EditableTextCell


def main(page: ft.Page):
    page.title = "spike: editable cells"
    page.window.width = 600
    page.window.height = 300

    log = ft.Text(value="(saved values appear here)")

    def save(field_name):
        return lambda new_value: setattr(log, "value",
            f"saved {field_name}={new_value!r}") or log.update()

    page.add(
        ft.Column([
            ft.Text("Click any cell to edit. Tab/Enter to save, Esc to cancel.",
                    size=14),
            EditableTextCell("foo", save("a")),
            EditableTextCell("", save("b"), placeholder="(empty)"),
            EditableTextCell("123.45", save("c")),
            log,
        ]),
    )


if __name__ == "__main__":
    ft.app(target=main)
