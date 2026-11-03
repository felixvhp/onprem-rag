from __future__ import annotations

from abc import ABC, abstractmethod

from llama_index.core import Document


class BaseSource(ABC):
    """A system that can be indexed in full and, optionally, one item at a time."""

    name: str = "base"

    @abstractmethod
    def load_all(self) -> list[Document]:
        """Fetch everything and return chunked documents."""

    def load_one(self, ref: str) -> list[Document]:
        """Fetch a single item (page, record, file) identified by ``ref``."""
        raise NotImplementedError

    def doc_prefix(self, ref: str) -> str:
        """Chunk-id prefix shared by every chunk of the item ``ref``."""
        return ref
