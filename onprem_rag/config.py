"""Runtime settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    storage_dir: str = "./storage"
    embed_model: str = "BAAI/bge-small-en-v1.5"  # any sentence-transformers model, or "hashing"
    llm_backend: str = "auto"  # "ollama", "extractive" or "auto" (ollama if reachable)
    ollama_model: str = "llama3.1:8b"
    ollama_url: str = "http://localhost:11434"
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 50
    similarity_top_k: int = 6
    model_id: str = "onprem-rag"
    domain: str = "the organisation's internal documentation"
    cite_sources: bool = True
    slack_webhook_url: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            storage_dir=os.getenv("STORAGE_DIR", "./storage"),
            embed_model=os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
            llm_backend=os.getenv("LLM_BACKEND", "auto"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            chunk_max_tokens=int(os.getenv("CHUNK_MAX_TOKENS", "512")),
            chunk_overlap_tokens=int(os.getenv("CHUNK_OVERLAP_TOKENS", "50")),
            similarity_top_k=int(os.getenv("TOP_K", "6")),
            model_id=os.getenv("MODEL_ID", "onprem-rag"),
            domain=os.getenv("ASSISTANT_DOMAIN", "the organisation's internal documentation"),
            cite_sources=_env_bool("CITE_SOURCES", True),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
