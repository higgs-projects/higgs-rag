from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.rag.models.document import Document


class BaseVector(ABC):
    def __init__(self, collection_name: str):
        self._collection_name = collection_name

    @abstractmethod
    def get_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def search_by_hybrid(self, query: str, query_vector: list[float], **kwargs: Any) -> list[Document]:
        raise NotImplementedError

    @property
    def collection_name(self):
        return self._collection_name
