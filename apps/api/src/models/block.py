from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.models.locator import Locator


class TextBlock(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    text: str
    locator: Locator
