from __future__ import annotations

import csv as csv_stdlib
from pathlib import Path

from src.models.block import TextBlock
from src.models.enums import FileType
from src.models.locator import CsvLocator
from src.parsers.common import ParsedDocument

_DIALECT_FIELDS = (
    "delimiter",
    "quotechar",
    "escapechar",
    "doublequote",
    "skipinitialspace",
    "lineterminator",
    "quoting",
)

_DEFAULT_DIALECT_KWARGS: dict = {
    "delimiter": ",",
    "quotechar": '"',
    "escapechar": None,
    "doublequote": True,
    "skipinitialspace": False,
    "lineterminator": "\r\n",
    "quoting": csv_stdlib.QUOTE_MINIMAL,
}


def dialect_to_kwargs(dialect: csv_stdlib.Dialect) -> dict:
    """Turn a csv.Dialect (or Sniffer result) into a plain, JSON-friendly
    dict of the fmtparams csv.reader/csv.writer accept, so it can be stashed
    on the job record and reused verbatim at correction time instead of
    re-sniffing (which could, in principle, land on a different dialect)."""

    return {field: getattr(dialect, field) for field in _DIALECT_FIELDS}


def sniff_dialect_kwargs(sample: str) -> dict:
    if not sample.strip():
        return dict(_DEFAULT_DIALECT_KWARGS)
    try:
        dialect = csv_stdlib.Sniffer().sniff(sample)
        return dialect_to_kwargs(dialect)
    except csv_stdlib.Error:
        return dict(_DEFAULT_DIALECT_KWARGS)


def parse(path: Path) -> ParsedDocument:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    dialect_kwargs = sniff_dialect_kwargs(raw)

    blocks: list[TextBlock] = []
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        reader = csv_stdlib.reader(f, **dialect_kwargs)
        for row_idx, row in enumerate(reader):
            for col_idx, value in enumerate(row):
                if value == "":
                    continue
                blocks.append(
                    TextBlock(
                        id=f"r{row_idx}c{col_idx}",
                        text=value,
                        locator=CsvLocator(row=row_idx, column=col_idx),
                    )
                )

    return ParsedDocument(
        file_type=FileType.CSV,
        blocks=blocks,
        meta={"dialect": dialect_kwargs},
    )
