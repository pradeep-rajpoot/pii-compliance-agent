from pathlib import Path

from src.models.enums import FileType
from src.models.locator import JsonLocator
from src.parsers import json as json_parser


def test_json_parse_blocks_and_locators(fixtures_dir: Path):
    doc = json_parser.parse(fixtures_dir / "sample.json")

    assert doc.file_type == FileType.JSON
    by_id = {b.id: b for b in doc.blocks}

    assert by_id["user.email"].text == "jane.doe@example.com"
    locator = by_id["user.email"].locator
    assert isinstance(locator, JsonLocator)
    assert locator.path == ["user", "email"]

    # Array element path -- id uses bracket notation, locator.path keeps
    # the raw int index for correction to re-walk.
    assert by_id["contacts[0].phone"].text == "555-010-1234"
    assert by_id["contacts[0].phone"].locator.path == ["contacts", 0, "phone"]

    # Non-string scalar leaves are stringified for detection, same as
    # xlsx/csv cells.
    assert by_id["active"].text == "True"


def test_json_parse_skips_null_and_empty_leaves(fixtures_dir: Path):
    doc = json_parser.parse(fixtures_dir / "sample.json")
    ids = {b.id for b in doc.blocks}

    assert "null_field" not in ids
    assert "empty_field" not in ids
