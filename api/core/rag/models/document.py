from typing import Optional

from pydantic import BaseModel


class ChildDocument(BaseModel):
    """Class for storing a piece of text and associated metadata."""

    page_content: str

    vector: Optional[list[float]] = None

    """Arbitrary metadata about the page content (e.g., source, relationships to other
        documents, etc.).
    """
    metadata: dict = {}


class Document(BaseModel):
    """Class for storing a piece of text and associated metadata."""

    page_content: str

    vector: Optional[list[float]] = None

    """Arbitrary metadata about the page content (e.g., source, relationships to other
        documents, etc.).
    """
    metadata: dict = {}

    provider: Optional[str] = "dify"

    children: Optional[list[ChildDocument]] = None
