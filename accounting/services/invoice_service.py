"""Invoice CRUD."""
import sqlite3
from typing import List, Optional

from accounting.models import Invoice


def create_invoice(conn: sqlite3.Connection, project_id: int, file_name: str,
                   invoice_no: Optional[str] = None,
                   invoice_date: Optional[str] = None,
                   invoice_date_iso: Optional[str] = None,
                   seller: Optional[str] = None,
                   amount: Optional[float] = None,
                   remark: Optional[str] = None,
                   taobao_order: Optional[str] = None,
                   status: str = "未报销") -> Invoice:
    cur = conn.execute(
        """
        INSERT INTO invoice(project_id, file_name, invoice_no, invoice_date,
                            invoice_date_iso, seller, amount, remark,
                            taobao_order, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, file_name, invoice_no, invoice_date, invoice_date_iso,
         seller, amount, remark, taobao_order, status),
    )
    conn.commit()
    return get_invoice(conn, cur.lastrowid)


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> Optional[Invoice]:
    row = conn.execute(
        "SELECT * FROM invoice WHERE id = ?", (invoice_id,)
    ).fetchone()
    return Invoice.from_row(row) if row else None


def list_invoices(conn: sqlite3.Connection, project_id: int) -> List[Invoice]:
    rows = conn.execute(
        """
        SELECT * FROM invoice WHERE project_id = ?
        ORDER BY invoice_date_iso DESC, id DESC
        """,
        (project_id,),
    ).fetchall()
    return [Invoice.from_row(r) for r in rows]
