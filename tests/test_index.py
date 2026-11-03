import os

from llama_index.core import Document

from onprem_rag.embedding import HashingEmbedding
from onprem_rag.index import RagIndex
from onprem_rag.llm import ExtractiveLLM


def test_retrieval_finds_the_right_page(index):
    nodes = index.retrieve("How long does a full charge take?", top_k=3)
    assert any(n.node.metadata["title"] == "Atlas AMR Overview" for n in nodes)


def test_answer_contains_context_and_sources(index):
    answer = index.answer("What is the API rate limit?")
    assert "600 requests per minute" in answer
    assert "Sources:" in answer and "Operator Console API" in answer


def test_persist_and_load_roundtrip(index, settings):
    assert os.path.exists(os.path.join(settings.storage_dir, "documents.json"))
    embed = HashingEmbedding()
    reloaded = RagIndex(settings, embed, embed.embed_dim, ExtractiveLLM())
    assert reloaded.load() is True
    assert reloaded.stats()["total_chunks"] == index.stats()["total_chunks"]
    assert "600 requests per minute" in reloaded.answer("What is the API rate limit?")


def test_replace_and_remove_by_prefix(index):
    before = index.stats()["total_chunks"]
    new_doc = Document(text="The new rate limit is 9000 requests per minute.", doc_id="operator-console-api.md#chunk0", metadata={"title": "Operator Console API", "url": "operator-console-api.md"})
    b, a = index.replace("operator-console-api.md", [new_doc])
    assert b == before and a < before
    assert "9000 requests per minute" in index.answer("What is the API rate limit?")
    _, after_remove = index.remove("operator-console-api.md")
    assert after_remove == a - 1


def test_load_returns_false_on_empty_storage(settings):
    embed = HashingEmbedding()
    rag = RagIndex(settings, embed, embed.embed_dim, ExtractiveLLM())
    assert rag.load() is False and rag.ready is False
