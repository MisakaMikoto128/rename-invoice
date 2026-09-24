"""Click-to-edit text cell. Click → swap Text for TextField → on submit/blur → save callback."""
from typing import Callable, Optional
import flet as ft


class EditableTextCell(ft.Container):
    """
    Display value as Text. Click swaps in TextField. Enter / lose focus → on_save(new_value).
    Esc → revert without saving.
    """

    def __init__(self, value: Optional[str], on_save: Callable[[str], None],
                 placeholder: str = "—"):
        super().__init__()
        self._value = value or ""
        self._on_save = on_save
        self._placeholder = placeholder
        self._build_view()

    def _build_view(self):
        text = self._value if self._value else self._placeholder
        color = ft.Colors.ON_SURFACE if self._value else ft.Colors.OUTLINE
        self.content = ft.Text(text, color=color)
        self.on_click = self._enter_edit
        self.padding = 6

    def _enter_edit(self, _e):
        self._tf = ft.TextField(
            value=self._value, autofocus=True, dense=True,
            on_submit=self._commit, on_blur=self._commit,
        )
        self.content = self._tf
        self.on_click = None
        self.update()

    def _commit(self, _e):
        new_value = self._tf.value
        if new_value != self._value:
            self._value = new_value
            self._on_save(new_value)
        self._build_view()
        self.update()
