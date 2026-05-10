"""Wrap rename_invoice.extract_invoice_metadata + add ISO date for storage."""
import re
import sys
from pathlib import Path
from typing import Optional

# rename_invoice.py 在 repo 根, 不是 package - 把 repo 根加进 sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import rename_invoice  # noqa: E402


_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def chinese_date_to_iso(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def extract(pdf_path: Path) -> dict:
    """
    返回 dict, 多一个 invoice_date_iso (派生自 date) 用于 sqlite 排序/索引.
    rename_invoice 原来的字段 (amount/amount_reason/invoice_no/date/seller) 全保留.
    """
    meta = rename_invoice.extract_invoice_metadata(Path(pdf_path))
    meta["invoice_date_iso"] = chinese_date_to_iso(meta.get("date"))
    return meta
