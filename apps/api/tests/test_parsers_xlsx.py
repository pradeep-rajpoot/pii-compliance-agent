from pathlib import Path

from src.models.enums import FileType
from src.models.locator import XlsxLocator
from src.parsers import xlsx


def test_xlsx_parse_blocks_and_locators(fixtures_dir: Path):
    doc = xlsx.parse(fixtures_dir / "sample.xlsx")

    assert doc.file_type == FileType.XLSX
    by_id = {b.id: b for b in doc.blocks}

    assert by_id["Sheet1!A1"].text == "Name"
    assert by_id["Sheet1!B2"].text == "john.smith@example.com"
    locator = by_id["Sheet1!B2"].locator
    assert isinstance(locator, XlsxLocator)
    assert locator.sheet == "Sheet1"
    assert locator.cell == "B2"


def test_xlsx_parse_keeps_formula_preserving_workbook_in_meta(fixtures_dir: Path):
    doc = xlsx.parse(fixtures_dir / "sample.xlsx")

    workbook = doc.meta["workbook"]
    assert workbook is not None
    ws = workbook["Sheet1"]
    # The formula-mode workbook must retain the literal formula string,
    # not a cached computed value.
    assert str(ws["B3"].value).startswith("=")
