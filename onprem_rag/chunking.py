"""Structure-aware chunking: split on section headings, then pack sentences into
token-bounded chunks with sentence-level overlap.

Chunk ids are ``<doc_id>#chunk<n>`` so that every chunk of a document can be found
again (and replaced) by prefix when the document changes.
"""

from __future__ import annotations

import re
from typing import Iterable

import tiktoken
from llama_index.core import Document

_HEADER = re.compile(r"\n(#{1,6}|={2,6})\s*([^\n=#+]+?)\s*(?:#{1,6}|={2,6})?\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class SemanticChunker:
    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 50,
        skip_section_keywords: Iterable[str] = ("obsolete",),
        encoding_name: str = "cl100k_base",
    ) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.skip_section_keywords = tuple(k.lower() for k in skip_section_keywords)
        self.encoding = tiktoken.get_encoding(encoding_name)

    # ------------------------------------------------------------------ public
    def chunk(self, content: str, doc_id: str, metadata: dict) -> list[Document]:
        """Split ``content`` into section-aware chunks tagged with ``metadata``."""
        content = content.strip()
        if not content:
            return []

        documents: list[Document] = []
        chunk_index = 0
        for section, body in self._sections(content, metadata.get("title", "Introduction")):
            if any(k in section.lower() for k in self.skip_section_keywords):
                continue
            section_docs = self._chunk_section(body, doc_id, metadata, section, chunk_index)
            documents.extend(section_docs)
            chunk_index += len(section_docs)
        return documents

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    # ----------------------------------------------------------------- helpers
    def _sections(self, content: str, first_title: str) -> list[tuple[str, str]]:
        """Return (section title, section text) pairs in document order."""
        parts = _HEADER.split("\n" + content)
        sections: list[tuple[str, str]] = []
        preamble = parts[0].strip()
        if preamble:
            sections.append((first_title, preamble))
        for i in range(1, len(parts), 3):
            title = parts[i + 1].strip() if i + 1 < len(parts) else ""
            body = parts[i + 2].strip() if i + 2 < len(parts) else ""
            if body:
                sections.append((title or first_title, body))
        return sections

    def _chunk_section(
        self, text: str, doc_id: str, metadata: dict, section: str, start_index: int
    ) -> list[Document]:
        documents: list[Document] = []
        current = ""
        chunk_index = start_index

        for sentence in _SENTENCE.split(" ".join(text.split())):
            candidate = f"{current} {sentence}".strip() if current else sentence
            if current and self.count_tokens(candidate) > self.max_tokens:
                documents.append(self._make(current, doc_id, metadata, section, chunk_index))
                chunk_index += 1
                overlap = self._overlap_text(current)
                current = f"{overlap} {sentence}".strip() if overlap else sentence
            else:
                current = candidate

        if current.strip():
            documents.append(self._make(current, doc_id, metadata, section, chunk_index))
        return documents

    def _overlap_text(self, text: str) -> str:
        sentences = _SENTENCE.split(text)
        kept: list[str] = []
        tokens = 0
        for sentence in reversed(sentences):
            n = self.count_tokens(sentence)
            if tokens + n > self.overlap_tokens:
                break
            kept.insert(0, sentence)
            tokens += n
        return " ".join(kept).strip()

    def _make(self, text: str, doc_id: str, metadata: dict, section: str, index: int) -> Document:
        chunk_metadata = {
            **metadata,
            "section": section,
            "chunk_index": index,
            "token_count": self.count_tokens(text),
        }
        noisy = [k for k in chunk_metadata if k not in ("title", "section")]
        return Document(
            text=text.strip(),
            doc_id=f"{doc_id}#chunk{index}",
            metadata=chunk_metadata,
            # Only the title and section are useful to the embedding and the prompt;
            # urls, timestamps and counters would just add noise to both.
            excluded_embed_metadata_keys=noisy,
            excluded_llm_metadata_keys=noisy,
        )
