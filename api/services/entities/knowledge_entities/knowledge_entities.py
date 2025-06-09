from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel


class ParentMode(StrEnum):
    FULL_DOC = "full-doc"
    PARAGRAPH = "paragraph"


class PreProcessingRule(BaseModel):
    id: str
    enabled: bool


class Segmentation(BaseModel):
    separator: str = "\n"
    max_tokens: int
    chunk_overlap: int = 0


class Rule(BaseModel):
    pre_processing_rules: Optional[list[PreProcessingRule]] = None
    segmentation: Optional[Segmentation] = None
    parent_mode: Optional[Literal["full-doc", "paragraph"]] = None
    subchunk_segmentation: Optional[Segmentation] = None
