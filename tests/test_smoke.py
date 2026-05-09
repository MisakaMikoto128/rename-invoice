"""End-to-end smoke covering: schema -> project -> invoice -> search -> stats."""
from accounting import db
from accounting.services import project_service as ps
from accounting.services import invoice_service as ivs


def test_full_flow(temp_db_path):
    db.init_schema(str(temp_db_path))
    conn = db.connect(str(temp_db_path))
    try:
        p = ps.create_project(conn, name="11月报销", folder_path="C:/n11")
        ivs.create_invoice(conn, project_id=p.id, file_name="a.pdf",
                           invoice_no="2595", seller="A", amount=100.0,
                           status="已报销")
        ivs.create_invoice(conn, project_id=p.id, file_name="b.pdf",
                           invoice_no="2532", seller="B", amount=50.0,
                           status="未报销")

        assert len(ivs.list_invoices(conn, p.id)) == 2

        # search
        found = ivs.search_invoices(conn, "B")
        assert len(found) == 1
        assert found[0].seller == "B"

        # stats
        st = ivs.stats_by_invoice_status(conn)
        assert st["已报销"]["sum"] == 100.0
        assert st["未报销"]["sum"] == 50.0

        # status flow
        ivs.update_invoice_status(conn, found[0].id, "报销中")
        st = ivs.stats_by_invoice_status(conn)
        assert st["报销中"]["count"] == 1
        assert st["未报销"]["count"] == 0
    finally:
        conn.close()
