from pathlib import Path

from src.models.enums import FileType
from src.models.locator import PdfLocator
from src.parsers import pdf


def test_pdf_parse_produces_one_block_per_nonempty_page(fixtures_dir: Path):
    doc = pdf.parse(fixtures_dir / "sample.pdf")

    assert doc.file_type == FileType.PDF
    assert doc.meta["total_pages"] == 2
    assert len(doc.blocks) == 2

    page1 = doc.blocks[0]
    assert page1.id == "page-1"
    assert isinstance(page1.locator, PdfLocator)
    assert page1.locator.page == 1
    assert "jane.doe@example.com" in page1.text
    assert "555-010-1234" in page1.text

    page2 = doc.blocks[1]
    assert page2.id == "page-2"
    assert page2.locator.page == 2
    assert "widgets" in page2.text
