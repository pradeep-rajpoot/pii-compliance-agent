from __future__ import annotations

from pathlib import Path

import pdfplumber

from src.models.block import TextBlock
from src.models.enums import FileType
from src.models.locator import PdfLocator
from src.parsers.common import ParsedDocument


def parse(path: Path) -> ParsedDocument:
    blocks: list[TextBlock] = []
    total_pages = 0

    with pdfplumber.open(str(path)) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            blocks.append(
                TextBlock(
                    id=f"page-{i}",
                    text=text,
                    locator=PdfLocator(page=i, bbox=None),
                )
            )

    return ParsedDocument(
        file_type=FileType.PDF,
        blocks=blocks,
        meta={"total_pages": total_pages},
    )
