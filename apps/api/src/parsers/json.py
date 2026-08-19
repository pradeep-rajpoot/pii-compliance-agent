from __future__ import annotations

import json as json_stdlib
from pathlib import Path
from typing import Any

from src.models.block import TextBlock
from src.models.enums import FileType
from src.models.locator import JsonLocator
from src.parsers.common import ParsedDocument

PathSegment = str | int


def _path_to_id(path: list[PathSegment]) -> str:
    """Render a path as a short, readable dotted/bracket id, e.g.
    "users[0].email" -- mirrors common JS/JSONPath-ish notation so the
    frontend's block id doubles as a human-readable locator."""

    parts: list[str] = []
    for segment in path:
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
        else:
            parts.append(f".{segment}" if parts else str(segment))
    return "".join(parts) or "$"


def _walk(value: Any, path: list[PathSegment], blocks: list[TextBlock]) -> None:
    if isinstance(value, dict):
        for key, sub_value in value.items():
            _walk(sub_value, [*path, key], blocks)
    elif isinstance(value, list):
        for idx, sub_value in enumerate(value):
            _walk(sub_value, [*path, idx], blocks)
    elif value is None:
        return
    else:
        # Leaf scalar (str/int/float/bool). Non-string leaves (a phone
        # number stored as a JSON number, say) are stringified for
        # detection the same way xlsx/csv cells are -- see parsers/xlsx.py.
        text = str(value)
        if text == "":
            return
        blocks.append(
            TextBlock(
                id=_path_to_id(path),
                text=text,
                locator=JsonLocator(path=list(path)),
            )
        )


def parse(path: Path) -> ParsedDocument:
    data = json_stdlib.loads(path.read_text(encoding="utf-8"))
    blocks: list[TextBlock] = []
    _walk(data, [], blocks)
    return ParsedDocument(file_type=FileType.JSON, blocks=blocks, meta={})
