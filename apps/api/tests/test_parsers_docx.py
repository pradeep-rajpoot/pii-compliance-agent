from pathlib import Path

from src.models.enums import FileType
from src.models.locator import DocxLocator
from src.parsers import docx


def test_docx_parse_blocks_and_run_offsets(fixtures_dir: Path):
    doc = docx.parse(fixtures_dir / "sample.docx")

    assert doc.file_type == FileType.DOCX
    by_id = {b.id: b for b in doc.blocks}

    assert "p0" in by_id
    assert by_id["p0"].text == "Contact: jane.doe@example.com please call soon."
    assert isinstance(by_id["p0"].locator, DocxLocator)
    assert by_id["p0"].locator.paragraph == 0

    run_offsets = doc.meta["run_offsets"]["p0"]
    # Two runs, contiguous, covering the whole paragraph text.
    assert run_offsets[0][1] == 0
    assert run_offsets[-1][2] == len(by_id["p0"].text)
    for i in range(len(run_offsets) - 1):
        assert run_offsets[i][2] == run_offsets[i + 1][1]


def test_docx_parse_no_pii_file(fixtures_dir: Path):
    doc = docx.parse(fixtures_dir / "no_pii.docx")
    assert len(doc.blocks) == 2
    assert all("@" not in b.text for b in doc.blocks)
