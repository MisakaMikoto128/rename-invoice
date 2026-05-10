from accounting.ui.widgets.status_chip import status_color
from accounting.ui.widgets.amount_text import format_amount


def test_status_color_known():
    assert status_color("未报销") == "#9E9E9E"
    assert status_color("报销中") == "#1976D2"
    assert status_color("已报销") == "#2E7D32"


def test_status_color_unknown_falls_back():
    assert status_color("胡说") == "#9E9E9E"


def test_format_amount_none():
    assert format_amount(None) == "—"


def test_format_amount_basic():
    assert format_amount(16.6) == "¥16.60"
    assert format_amount(905.34) == "¥905.34"


def test_format_amount_negative():
    assert format_amount(-100.5) == "-¥100.50"
