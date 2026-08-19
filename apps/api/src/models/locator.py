from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    type: Literal["pdf"] = "pdf"
    page: int
    bbox: tuple[float, float, float, float] | None = None


class XlsxLocator(BaseModel):
    type: Literal["xlsx"] = "xlsx"
    sheet: str
    cell: str


class CsvLocator(BaseModel):
    type: Literal["csv"] = "csv"
    row: int
    column: int


class DocxLocator(BaseModel):
    type: Literal["docx"] = "docx"
    paragraph: int | None = None
    table: int | None = None
    row: int | None = None
    cell: int | None = None


class JsonLocator(BaseModel):
    type: Literal["json"] = "json"
    # Sequence of dict keys (str) / list indices (int) from the document
    # root down to the leaf value, e.g. ["users", 0, "email"] for
    # `{"users": [{"email": "..."}]}`. Correction re-walks this path to
    # splice the masked value back into the same spot.
    path: list[str | int]


Locator = Annotated[
    Union[PdfLocator, XlsxLocator, CsvLocator, DocxLocator, JsonLocator],
    Field(discriminator="type"),
]


def locator_dump(
    locator: PdfLocator | XlsxLocator | CsvLocator | DocxLocator | JsonLocator,
) -> dict:
    """Serialize a locator excluding unset/None fields (e.g. DocxLocator only
    populates the paragraph OR table/row/cell fields that apply)."""

    return locator.model_dump(exclude_none=True)
