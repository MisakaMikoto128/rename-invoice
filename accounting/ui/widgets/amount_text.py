"""¥X.XX display helper."""
from typing import Optional


def format_amount(amount: Optional[float]) -> str:
    if amount is None:
        return "—"
    if amount < 0:
        return f"-¥{abs(amount):,.2f}"
    return f"¥{amount:,.2f}"
