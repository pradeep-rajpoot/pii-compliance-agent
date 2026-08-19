from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.models.block import TextBlock
from src.models.enums import FileType


@dataclass
class ParsedDocument:
    file_type: FileType
    blocks: list[TextBlock]
    meta: dict[str, Any] = field(default_factory=dict)


class Parser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...


_REGISTRY: dict[FileType, Parser] = {}


def register_parser(file_type: FileType, parser: Parser) -> None:
    _REGISTRY[file_type] = parser


def get_parser(file_type: FileType) -> Parser:
    return _REGISTRY[file_type]
