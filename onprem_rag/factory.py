"""Wire settings, embedding, LLM, source and index together."""

from __future__ import annotations

import os

from .chunking import SemanticChunker
from .config import Settings
from .embedding import build_embedding
from .index import RagIndex
from .llm import build_llm
from .sources.base import BaseSource
from .sources.local_docs import LocalDocsSource


def build_chunker(settings: Settings) -> SemanticChunker:
    return SemanticChunker(max_tokens=settings.chunk_max_tokens, overlap_tokens=settings.chunk_overlap_tokens)


def build_source(kind: str, settings: Settings, path: str | None = None) -> BaseSource:
    chunker = build_chunker(settings)
    if kind == "local":
        return LocalDocsSource(path or os.getenv("DOCS_PATH", "./docs"), chunker)
    if kind == "mediawiki":
        from .sources.mediawiki import MediaWikiSource

        return MediaWikiSource.from_env(chunker)
    if kind == "suitecrm":
        from .sources.suitecrm import SuiteCRMSource

        return SuiteCRMSource.from_env()
    if kind == "gitlab":
        from .sources.gitlab import GitLabSource

        return GitLabSource.from_env(chunker)
    raise ValueError(f"Unknown source kind: {kind}")


def build_index(settings: Settings) -> RagIndex:
    embed_model, dim = build_embedding(settings.embed_model)
    llm = build_llm(settings.llm_backend, settings.ollama_model, settings.ollama_url)
    return RagIndex(settings, embed_model, dim, llm)


def load_or_build(index: RagIndex, source: BaseSource, rebuild: bool = False) -> RagIndex:
    if rebuild or not index.load():
        index.build(source.load_all())
    return index
