"""Invoice CRUD."""
import shutil
import sqlite3
from pathlib import Path
from typing import List, Optional

from accounting import extractor  # noqa: F401  (also patches sys.path for rename_invoice)
from accounting.models import Invoice, VALID_STATUS
from rename_invoice import ALREADY_PREFIXED_RE


# 仅允许编辑这几列, 防 SQL 注入 (column 名从 UI 来)
EDITABLE_COLUMNS = (
    "invoice_no", "invoice_date", "invoice_date_iso",
    "seller", "amount", "remark", "taobao_order",
)


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


def update_invoice_field(conn: sqlite3.Connection, invoice_id: int,
                         column: str, value) -> None:
    if column not in EDITABLE_COLUMNS:
        raise ValueError(f"Column not editable: {column!r}")
    conn.execute(
        f"UPDATE invoice SET {column} = ?, updated_at = CURRENT_TIMESTAMP "
        f"WHERE id = ?",
        (value, invoice_id),
    )
    conn.commit()


def update_invoice_status(conn: sqlite3.Connection, invoice_id: int,
                          status: str) -> None:
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status!r}")
    conn.execute(
        "UPDATE invoice SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, invoice_id),
    )
    conn.commit()


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    conn.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
    conn.commit()


def search_invoices(conn: sqlite3.Connection, query: str,
                    project_id: Optional[int] = None) -> List[Invoice]:
    """模糊匹配 invoice_no / seller / remark / taobao_order / file_name."""
    pattern = f"%{query}%"
    sql = """
        SELECT * FROM invoice
        WHERE (invoice_no LIKE ? OR seller LIKE ? OR remark LIKE ?
               OR taobao_order LIKE ? OR file_name LIKE ?)
    """
    args: list = [pattern] * 5
    if project_id is not None:
        sql += " AND project_id = ?"
        args.append(project_id)
    sql += " ORDER BY invoice_date_iso DESC, id DESC"
    rows = conn.execute(sql, tuple(args)).fetchall()
    return [Invoice.from_row(r) for r in rows]


def stats_by_invoice_status(conn: sqlite3.Connection,
                            project_id: Optional[int] = None) -> dict:
    """{status: {count, sum}}; 三个 status 都有 (无数据时 0)."""
    out = {s: {"count": 0, "sum": 0.0} for s in VALID_STATUS}
    sql = "SELECT status, COUNT(*) c, COALESCE(SUM(amount), 0) s FROM invoice"
    args: tuple = ()
    if project_id is not None:
        sql += " WHERE project_id = ?"
        args = (project_id,)
    sql += " GROUP BY status"
    for row in conn.execute(sql, args):
        out[row["status"]] = {"count": row["c"], "sum": float(row["s"])}
    return out


def stats_by_project_status(conn: sqlite3.Connection) -> dict:
    """{project.status: {count: 项目数, sum: 项目下发票总金额}}."""
    out = {s: {"count": 0, "sum": 0.0} for s in VALID_STATUS}
    sql = """
        SELECT p.status,
               COUNT(DISTINCT p.id) c,
               COALESCE(SUM(i.amount), 0) s
        FROM project p
        LEFT JOIN invoice i ON i.project_id = p.id
        GROUP BY p.status
    """
    for row in conn.execute(sql):
        out[row["status"]] = {"count": row["c"], "sum": float(row["s"])}
    return out


def update_invoice_fields(conn: sqlite3.Connection, invoice_id: int,
                          **changes) -> None:
    """批量更新可编辑字段; 校验所有 column 在 EDITABLE_COLUMNS 内."""
    if not changes:
        return
    for col in changes:
        if col not in EDITABLE_COLUMNS:
            raise ValueError(f"Column not editable: {col!r}")
    sets = ", ".join(f"{col} = ?" for col in changes) + ", updated_at = CURRENT_TIMESTAMP"
    args = tuple(changes.values()) + (invoice_id,)
    conn.execute(f"UPDATE invoice SET {sets} WHERE id = ?", args)
    conn.commit()


def import_pdf(conn: sqlite3.Connection, project_id: int,
               pdf_path: Path,
               copy_to: Optional[Path] = None,
               rename: bool = True,
               dedupe: bool = True) -> Optional[Invoice]:
    """读 PDF -> 提字段 -> (按发票号去重) -> (可选改名加 ¥前缀) -> (可选拷贝) -> INSERT.

    返回新建的 Invoice; 如 dedupe 命中已存在的 invoice_no, 返回 None.
    """
    src = Path(pdf_path)
    meta = extractor.extract(src)

    if dedupe and meta.get("invoice_no"):
        existing = conn.execute(
            "SELECT id FROM invoice WHERE project_id = ? AND invoice_no = ?",
            (project_id, meta["invoice_no"]),
        ).fetchone()
        if existing is not None:
            return None  # 同项目内已存在该 invoice_no, 跳过 (不复制不入库)

    target_basename = src.name
    if copy_to is not None and rename and meta.get("amount"):
        if not ALREADY_PREFIXED_RE.match(src.name):
            target_basename = f"{meta['amount']}元-{src.name}"

    if copy_to is not None:
        dest_dir = Path(copy_to)
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / target_basename
        if target.exists():
            stem = Path(target_basename).stem
            suffix = Path(target_basename).suffix
            n = 2
            while True:
                candidate = dest_dir / f"{stem} ({n}){suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                n += 1
        shutil.copy2(src, target)
        file_name = target.name
    else:
        file_name = target_basename

    amt: Optional[float] = None
    if meta.get("amount"):
        try:
            amt = float(meta["amount"])
        except (TypeError, ValueError):
            amt = None
    return create_invoice(
        conn, project_id=project_id, file_name=file_name,
        invoice_no=meta.get("invoice_no"),
        invoice_date=meta.get("date"),
        invoice_date_iso=meta.get("invoice_date_iso"),
        seller=meta.get("seller"),
        amount=amt,
    )
