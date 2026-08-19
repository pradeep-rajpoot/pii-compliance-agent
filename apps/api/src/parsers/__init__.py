from __future__ import annotations

from pathlib import Path

from src.models.enums import FileType
from src.parsers import csv as csv_parser
from src.parsers import docx as docx_parser
from src.parsers import json as json_parser
from src.parsers import pdf as pdf_parser
from src.parsers import xlsx as xlsx_parser
from src.parsers.common import ParsedDocument, get_parser, register_parser

register_parser(FileType.PDF, pdf_parser)
register_parser(FileType.XLSX, xlsx_parser)
register_parser(FileType.XLS, xlsx_parser)
register_parser(FileType.CSV, csv_parser)
register_parser(FileType.DOCX, docx_parser)
register_parser(FileType.JSON, json_parser)


def parse_file(file_type: FileType, path: Path) -> ParsedDocument:
    parser = get_parser(file_type)
    return parser.parse(path)


__all__ = ["parse_file", "get_parser", "register_parser", "ParsedDocument"]
