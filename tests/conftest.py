import os

import pytest

from onprem_rag.chunking import SemanticChunker
from onprem_rag.config import Settings
from onprem_rag.embedding import HashingEmbedding
from onprem_rag.index import RagIndex
from onprem_rag.llm import ExtractiveLLM
from onprem_rag.sources.local_docs import LocalDocsSource

CORPUS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo", "corpus")


@pytest.fixture
def settings(tmp_path):
    return Settings(storage_dir=str(tmp_path / "storage"), embed_model="hashing", llm_backend="extractive", similarity_top_k=4, domain="the test corpus")


@pytest.fixture
def chunker():
    return SemanticChunker(max_tokens=120, overlap_tokens=20)


@pytest.fixture
def source(chunker):
    return LocalDocsSource(CORPUS, chunker)


@pytest.fixture
def index(settings, source):
    embed = HashingEmbedding()
    rag = RagIndex(settings, embed, embed.embed_dim, ExtractiveLLM())
    rag.build(source.load_all())
    return rag
