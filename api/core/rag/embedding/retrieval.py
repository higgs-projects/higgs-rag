from typing import Optional

from pydantic import BaseModel

from models.dataset import Document, DocumentSegment


class RetrievalChildChunk(BaseModel):
    """Retrieval segments."""

    id: str
    content: str
    score: float
    position: int


class RetrievalSegments(BaseModel):
    """Retrieval segments."""

    model_config = {"arbitrary_types_allowed": True}
    document: Document
    segment: DocumentSegment
    child_chunks: Optional[list[RetrievalChildChunk]] = None
    score: Optional[float] = None
