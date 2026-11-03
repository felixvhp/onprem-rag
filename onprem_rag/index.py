"""FAISS-backed vector index with persistence, incremental document replacement
and a streaming question-answering engine.

FAISS flat indexes are immutable, so an update removes the affected document's
chunks from the in-memory document list and rebuilds the index. That is simple
and correct for knowledge bases of tens of thousands of chunks; a mutable vector
store is the natural next step for larger corpora.
"""

from __future__ import annotations

import json
import os
from typing import Iterable, Iterator

import faiss
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import LLM
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.prompts import PromptTemplate
from llama_index.vector_stores.faiss import FaissVectorStore

from .config import Settings as AppSettings
from .llm import CONTEXT_SEPARATOR
from .logging_setup import logger

_DOCUMENTS_FILE = "documents.json"

QA_PROMPT = (
    "You are an assistant for {domain}. Use only the context below to answer; "
    "if the context does not contain the answer, say that you do not know.\n"
    f"{CONTEXT_SEPARATOR}\n"
    "{{context_str}}\n"
    f"{CONTEXT_SEPARATOR}\n"
    "Answer the question clearly and concisely, and mention the page a fact comes "
    "from when that helps the reader.\n"
    "Query: {{query_str}}\n"
    "Answer: "
)


class RagIndex:
    def __init__(self, settings: AppSettings, embed_model: BaseEmbedding, embed_dim: int, llm: LLM) -> None:
        self.settings = settings
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.llm = llm
        self.documents: list[Document] = []
        self.index: VectorStoreIndex | None = None
        self._query_engine = None
        # Chunks are produced upstream; the splitter only guards against oversized inputs.
        self._transformations = [SentenceSplitter(chunk_size=4096, chunk_overlap=0)]
        Settings.embed_model = embed_model
        Settings.llm = llm

    # ----------------------------------------------------------------- building
    def build(self, documents: Iterable[Document]) -> None:
        self.documents = list(documents)
        logger.info("Building FAISS index from %d chunks", len(self.documents))
        vector_store = FaissVectorStore(faiss_index=faiss.IndexFlatL2(self.embed_dim))
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self.index = VectorStoreIndex.from_documents(
            self.documents,
            storage_context=storage_context,
            embed_model=self.embed_model,
            transformations=self._transformations,
        )
        self.persist()
        self._query_engine = self._make_query_engine()

    def load(self) -> bool:
        """Load a persisted index. Returns False when nothing usable is on disk."""
        storage_dir = self.settings.storage_dir
        documents_file = os.path.join(storage_dir, _DOCUMENTS_FILE)
        if not (os.path.isdir(storage_dir) and os.path.exists(documents_file)):
            return False
        try:
            vector_store = FaissVectorStore.from_persist_dir(storage_dir)
            storage_context = StorageContext.from_defaults(vector_store=vector_store, persist_dir=storage_dir)
            self.index = load_index_from_storage(storage_context, embed_model=self.embed_model)
            with open(documents_file, encoding="utf-8") as handle:
                self.documents = [Document.from_dict(d) for d in json.load(handle)]
            self._query_engine = self._make_query_engine()
            logger.info("Loaded persisted index with %d chunks from %s", len(self.documents), storage_dir)
            return True
        except Exception as exc:  # noqa: BLE001 - a corrupt store should fall back to a rebuild
            logger.warning("Could not load persisted index (%s); it will be rebuilt", exc)
            self.index = None
            self.documents = []
            return False

    def persist(self) -> None:
        storage_dir = self.settings.storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        assert self.index is not None
        self.index.storage_context.persist(persist_dir=storage_dir)
        with open(os.path.join(storage_dir, _DOCUMENTS_FILE), "w", encoding="utf-8") as handle:
            json.dump([d.to_dict() for d in self.documents], handle)

    # ------------------------------------------------------------------ updates
    def replace(self, doc_prefix: str, new_documents: Iterable[Document]) -> tuple[int, int]:
        """Replace every chunk whose id starts with ``doc_prefix``. Returns (before, after)."""
        before = len(self.documents)
        kept = [d for d in self.documents if not d.doc_id.startswith(doc_prefix)]
        self.build(kept + list(new_documents))
        return before, len(self.documents)

    def remove(self, doc_prefix: str) -> tuple[int, int]:
        return self.replace(doc_prefix, [])

    # ------------------------------------------------------------------ queries
    @property
    def ready(self) -> bool:
        return self._query_engine is not None

    def query(self, question: str) -> Iterator[str]:
        """Stream the answer as text deltas; the last delta may be a sources line."""
        if self._query_engine is None:
            raise RuntimeError("Index is not built yet")
        response = self._query_engine.query(question)
        if getattr(response, "response_gen", None) is not None:
            for chunk in response.response_gen:
                yield chunk if isinstance(chunk, str) else str(chunk)
        else:
            yield str(response)
        if self.settings.cite_sources:
            sources = self._format_sources(getattr(response, "source_nodes", []) or [])
            if sources:
                yield f"\n\nSources: {sources}"

    def answer(self, question: str) -> str:
        return "".join(self.query(question))

    def retrieve(self, question: str, top_k: int) -> list:
        if self.index is None:
            raise RuntimeError("Index is not built yet")
        return self.index.as_retriever(similarity_top_k=top_k).retrieve(question)

    def stats(self) -> dict:
        titles = {d.metadata.get("title") for d in self.documents if d.metadata.get("title")}
        return {
            "total_chunks": len(self.documents),
            "total_documents": len(titles),
            "embedding_model": getattr(self.embed_model, "model_name", "unknown"),
            "llm": self.llm.metadata.model_name,
            "index_ready": self.ready,
        }

    # ------------------------------------------------------------------ helpers
    def _make_query_engine(self):
        prompt = PromptTemplate(QA_PROMPT.format(domain=self.settings.domain))
        return self.index.as_query_engine(
            llm=self.llm,
            response_mode="compact",
            similarity_top_k=self.settings.similarity_top_k,
            streaming=True,
            text_qa_template=prompt,
        )

    @staticmethod
    def _format_sources(source_nodes) -> str:
        seen: list[str] = []
        for node in source_nodes:
            meta = node.node.metadata if hasattr(node, "node") else {}
            title = meta.get("title") or meta.get("name") or ""
            url = meta.get("url", "")
            label = f"{title} ({url})" if title and url and url != title else (title or url)
            if label and label not in seen:
                seen.append(label)
        return "; ".join(seen[:5])
