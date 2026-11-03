"""Index a folder of Markdown or plain-text files. Used by the demo and tests, and
handy for any documentation that already lives in a repository."""

from __future__ import annotations

import os
import re

from llama_index.core import Document

from ..chunking import SemanticChunker
from ..logging_setup import logger
from .base import BaseSource

_EXTENSIONS = (".md", ".markdown", ".txt")
_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class LocalDocsSource(BaseSource):
    name = "local"

    def __init__(self, root: str, chunker: SemanticChunker, skip_obsolete: bool = True) -> None:
        self.root = os.path.abspath(root)
        self.chunker = chunker
        self.skip_obsolete = skip_obsolete

    def load_all(self) -> list[Document]:
        documents: list[Document] = []
        for dirpath, _, filenames in os.walk(self.root):
            for filename in sorted(filenames):
                if filename.lower().endswith(_EXTENSIONS):
                    rel = os.path.relpath(os.path.join(dirpath, filename), self.root)
                    documents.extend(self.load_one(rel))
        logger.info("Loaded %d chunks from %s", len(documents), self.root)
        return documents

    def load_one(self, ref: str) -> list[Document]:
        path = os.path.join(self.root, ref)
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        match = _TITLE.search(content)
        title = match.group(1).strip() if match else os.path.splitext(os.path.basename(ref))[0]
        if match:
            content = content[: match.start()] + content[match.end():]
        if self.skip_obsolete and ("obsolete" in title.lower() or "obsolete" in content.strip()[:200].lower()):
            logger.info("Skipping obsolete page %r", title)
            return []
        metadata = {"title": title, "url": ref, "source": self.name, "last_modified": _mtime(path)}
        return self.chunker.chunk(content, doc_id=ref, metadata=metadata)


def _mtime(path: str) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat(timespec="seconds")
