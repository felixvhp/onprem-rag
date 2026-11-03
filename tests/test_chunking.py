from onprem_rag.chunking import SemanticChunker

TEXT = """Intro sentence one. Intro sentence two.

## Setup
Setup sentence one. Setup sentence two. Setup sentence three.

## Obsolete notes
This should be skipped entirely.

## Usage
""" + " ".join(f"Usage sentence number {i}." for i in range(80))


def test_sections_become_chunks_with_metadata():
    chunker = SemanticChunker(max_tokens=60, overlap_tokens=10)
    docs = chunker.chunk(TEXT, doc_id="page", metadata={"title": "Page"})
    sections = {d.metadata["section"] for d in docs}
    assert {"Page", "Setup", "Usage"} <= sections
    assert "Obsolete notes" not in sections
    assert all(d.doc_id.startswith("page#chunk") for d in docs)
    assert [d.metadata["chunk_index"] for d in docs] == list(range(len(docs)))


def test_long_section_is_split_with_overlap_under_token_limit():
    chunker = SemanticChunker(max_tokens=60, overlap_tokens=10)
    docs = [d for d in chunker.chunk(TEXT, "page", {"title": "Page"}) if d.metadata["section"] == "Usage"]
    assert len(docs) > 1
    assert all(d.metadata["token_count"] <= 60 for d in docs)
    # the start of each chunk repeats the tail of the previous one
    for previous, current in zip(docs, docs[1:]):
        first_sentence = current.text.split(". ")[0]
        assert first_sentence in previous.text


def test_empty_content_yields_nothing():
    assert SemanticChunker().chunk("   ", "x", {}) == []
