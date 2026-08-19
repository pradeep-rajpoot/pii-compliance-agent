from pathlib import Path

from src.models.enums import FileType
from src.models.locator import CsvLocator
from src.parsers import csv as csv_parser


def test_csv_parse_blocks_and_locators(fixtures_dir: Path):
    doc = csv_parser.parse(fixtures_dir / "sample.csv")

    assert doc.file_type == FileType.CSV
    by_id = {b.id: b for b in doc.blocks}

    assert by_id["r0c0"].text == "name"
    assert by_id["r1c1"].text == "alice.example@example.com"
    locator = by_id["r1c1"].locator
    assert isinstance(locator, CsvLocator)
    assert locator.row == 1
    assert locator.column == 1

    assert "dialect" in doc.meta
    assert doc.meta["dialect"]["delimiter"] == ","


def test_csv_parse_empty_file_has_no_blocks(fixtures_dir: Path):
    doc = csv_parser.parse(fixtures_dir / "empty.csv")
    assert doc.blocks == []


def test_dialect_reused_not_resniffed(fixtures_dir: Path):
    doc = csv_parser.parse(fixtures_dir / "sample.csv")
    dialect_kwargs = doc.meta["dialect"]

    # Simulate correction-time reuse: read using the stored dialect kwargs
    # directly rather than re-sniffing.
    import csv as csv_stdlib

    with open(fixtures_dir / "sample.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv_stdlib.reader(f, **dialect_kwargs))

    assert rows[0] == ["name", "email", "notes"]
