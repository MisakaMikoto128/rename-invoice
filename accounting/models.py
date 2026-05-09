"""Plain dataclass models. created_at / updated_at remain ISO strings (sqlite TEXT)."""
from dataclasses import dataclass
from typing import Any, Mapping, Optional


VALID_STATUS = ("未报销", "报销中", "已报销")


@dataclass
class Project:
    id: Optional[int]
    name: str
    folder_path: str
    status: str = "未报销"
    note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Project":
        return cls(
            id=row["id"],
            name=row["name"],
            folder_path=row["folder_path"],
            status=row["status"],
            note=row["note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Invoice:
    id: Optional[int]
    project_id: int
    file_name: str
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_date_iso: Optional[str] = None
    seller: Optional[str] = None
    amount: Optional[float] = None
    remark: Optional[str] = None
    taobao_order: Optional[str] = None
    status: str = "未报销"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Invoice":
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            file_name=row["file_name"],
            invoice_no=row["invoice_no"],
            invoice_date=row["invoice_date"],
            invoice_date_iso=row["invoice_date_iso"],
            seller=row["seller"],
            amount=row["amount"],
            remark=row["remark"],
            taobao_order=row["taobao_order"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
