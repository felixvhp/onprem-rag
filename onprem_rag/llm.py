"""Language-model backends: a thin Ollama client and an extractive fallback that
returns the retrieved passages verbatim when no generative model is available."""

from __future__ import annotations

import json
import re
from typing import Any

import requests
from llama_index.core.llms import CompletionResponse, CompletionResponseGen, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback

from .logging_setup import logger

CONTEXT_SEPARATOR = "---------------------"


class OllamaLLM(CustomLLM):
    """Minimal wrapper around Ollama's ``/api/generate`` endpoint."""

    model_name: str = "llama3.1:8b"
    ollama_url: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 768
    timeout: int = 120

    @classmethod
    def class_name(cls) -> str:
        return "OllamaLLM"

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(context_window=8192, num_output=self.max_tokens, model_name=self.model_name)

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return CompletionResponse(text=response.json().get("response", ""))
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as text
            logger.error("Ollama completion failed: %s", exc)
            return CompletionResponse(text=f"Error: {exc}")

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponseGen:
        def generator() -> CompletionResponseGen:
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": True,
                        "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                    },
                    stream=True,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                text = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    delta = data.get("response", "")
                    if delta:
                        text += delta
                        yield CompletionResponse(text=text, delta=delta)
                    if data.get("done"):
                        break
            except Exception as exc:  # noqa: BLE001
                logger.error("Ollama streaming failed: %s", exc)
                yield CompletionResponse(text=f"Error: {exc}", delta=f"Error: {exc}")

        return generator()


class ExtractiveLLM(CustomLLM):
    """Fallback that answers with the retrieved context instead of generating.

    Useful for tests, for machines without a model server, and for checking what
    the retriever returns independently of the generator.
    """

    max_chars: int = 1500

    @classmethod
    def class_name(cls) -> str:
        return "ExtractiveLLM"

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(context_window=200_000, num_output=1024, model_name="extractive")

    def _answer(self, prompt: str) -> str:
        parts = prompt.split(CONTEXT_SEPARATOR)
        context = parts[1].strip() if len(parts) >= 3 else prompt.strip()
        context = re.sub(r"\n{3,}", "\n\n", context)
        if len(context) > self.max_chars:
            context = context[: self.max_chars].rstrip() + " [...]"
        return "No generative model is configured. The most relevant passages are:\n\n" + context

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        return CompletionResponse(text=self._answer(prompt))

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponseGen:
        answer = self._answer(prompt)

        def generator() -> CompletionResponseGen:
            words = answer.split(" ")
            text = ""
            for i in range(0, len(words), 5):
                delta = " ".join(words[i : i + 5]) + (" " if i + 5 < len(words) else "")
                text += delta
                yield CompletionResponse(text=text, delta=delta)

        return generator()


def ollama_available(url: str, timeout: float = 2.0) -> bool:
    try:
        return requests.get(f"{url}/api/tags", timeout=timeout).status_code == 200
    except requests.RequestException:
        return False


def build_llm(backend: str, ollama_model: str, ollama_url: str) -> CustomLLM:
    if backend == "auto":
        backend = "ollama" if ollama_available(ollama_url) else "extractive"
        logger.info("LLM backend resolved to '%s'", backend)
    if backend == "ollama":
        return OllamaLLM(model_name=ollama_model, ollama_url=ollama_url)
    if backend == "extractive":
        return ExtractiveLLM()
    raise ValueError(f"Unknown LLM backend: {backend}")
