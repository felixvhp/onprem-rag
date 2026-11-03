"""Embedding backends: a sentence-transformers model for real use, and a
dependency-free hashed bag-of-words embedding for tests and offline demos."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from llama_index.core.embeddings import BaseEmbedding

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from how i in is it its of on or that the this to was what when where which who why with do does did".split()
)


def _stem(token: str) -> str:
    """Crude suffix stripping, enough to match 'limits' with 'limit' and 'charging' with 'charge'."""
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            if suffix == "ies":
                token += "y"
            break
    return token


class HashingEmbedding(BaseEmbedding):
    """Deterministic unigram+bigram feature hashing, L2-normalised.

    Retrieval quality is lexical only, but it needs no model download, which keeps
    the test-suite and the offline demo self-contained.
    """

    embed_dim: int = 512

    def __init__(self, embed_dim: int = 512, **kwargs: Any) -> None:
        super().__init__(model_name="hashing", embed_dim=embed_dim, **kwargs)

    @classmethod
    def class_name(cls) -> str:
        return "HashingEmbedding"

    def _embed(self, text: str) -> list[float]:
        tokens = [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        counts: dict[str, int] = {}
        for feature in features:
            counts[feature] = counts.get(feature, 0) + 1
        vec = [0.0] * self.embed_dim
        for feature, count in counts.items():
            h = int(hashlib.md5(feature.encode()).hexdigest(), 16)
            vec[h % self.embed_dim] += (1.0 + math.log(count)) * (1.0 if (h >> 8) & 1 else -1.0)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)


def build_embedding(name: str) -> tuple[BaseEmbedding, int]:
    """Return (embedding model, vector dimension) for a settings value."""
    if name == "hashing":
        model = HashingEmbedding()
        return model, model.embed_dim
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    model = HuggingFaceEmbedding(model_name=name)
    dim = len(model.get_text_embedding("dimension probe"))
    return model, dim
