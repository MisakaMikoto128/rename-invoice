"""Pure helper + Flet badge for status."""
import flet as ft

_COLORS = {
    "未报销": "#9E9E9E",  # gray
    "报销中": "#1976D2",  # blue
    "已报销": "#2E7D32",  # green
}


def status_color(status: str) -> str:
    return _COLORS.get(status, "#9E9E9E")


def status_chip(status: str) -> ft.Container:
    """Pill-shaped status badge."""
    return ft.Container(
        content=ft.Text(status, color="white", size=12, weight=ft.FontWeight.W_500),
        bgcolor=status_color(status),
        padding=ft.padding.symmetric(horizontal=8, vertical=2),
        border_radius=10,
    )
