"""Verify extractor wraps rename_invoice + normalizes Chinese date."""
from pathlib import Path
import pytest
from accounting import extractor


SAMPLE_DIR = Path(__file__).parent / "_pdf_samples"


def test_chinese_date_to_iso():
    assert extractor.chinese_date_to_iso("2025年11月18日") == "2025-11-18"
    assert extractor.chinese_date_to_iso("2025年1月3日") == "2025-01-03"


def test_chinese_date_to_iso_none_or_garbage():
    assert extractor.chinese_date_to_iso(None) is None
    assert extractor.chinese_date_to_iso("") is None
    assert extractor.chinese_date_to_iso("乱码无日期") is None


def test_chinese_date_to_iso_embedded():
    """日期可能嵌在更长文本里, 应能提取."""
    assert extractor.chinese_date_to_iso("开票日期: 2025年11月18日") == "2025-11-18"


@pytest.mark.skipif(
    not SAMPLE_DIR.exists() or not list(SAMPLE_DIR.glob("*.pdf")),
    reason="no PDF samples in tests/_pdf_samples (gitignored). Drop a PDF in to run.",
)
def test_extract_returns_dict_with_keys():
    pdf = next(SAMPLE_DIR.glob("*.pdf"))
    meta = extractor.extract(pdf)
    assert "amount" in meta
    assert "invoice_no" in meta
    assert "date" in meta
    assert "seller" in meta
    assert "invoice_date_iso" in meta
