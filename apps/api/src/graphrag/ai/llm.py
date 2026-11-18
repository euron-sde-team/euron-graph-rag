"""Chat models behind one interface, for the extractor, the community reporter and answers.

Two wire formats cover most providers: the OpenAI-compatible Chat Completions API (OpenAI,
Groq, Together, Mistral, DeepSeek, OpenRouter, vLLM, LM Studio and others) and Ollama's native
/api/chat. With LLM_PROVIDER=local there is no client at all: every task has a deterministic
offline implementation instead (graph/extraction/local.py, graph/summaries.py,
graph/search/compose.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from graphrag.core.config import Settings
from graphrag.core.errors import UpstreamError
from graphrag.core.logging import get_logger

log = get_logger("graphrag.llm")


@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ChatClient(Protocol):
    provider: str
    default_model: str

    async def complete(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int
    ) -> tuple[str, Usage]: ...

    async def aclose(self) -> None: ...


class OpenAICompatibleClient:
    provider = "openai"

    def __init__(self, settings: Settings) -> None:
        self.default_model = settings.llm_model
        self._temperature = settings.llm_temperature
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url.rstrip("/"),
            headers={"authorization": f"Bearer {key}"} if key else {},
            timeout=httpx.Timeout(settings.llm_timeout_s, connect=10.0),
        )

    async def complete(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int
    ) -> tuple[str, Usage]:
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": max_tokens,
        }
        try:
            response = await self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise UpstreamError("The model provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("The model provider could not be reached.") from exc
        if response.status_code >= 400:
            log.warning("llm_error", status=response.status_code, detail=response.text[:300])
            raise UpstreamError(f"The model provider returned HTTP {response.status_code}.")
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamError("The model provider returned an unexpected response.") from exc
        reported = payload.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(reported.get("prompt_tokens", 0)),
            completion_tokens=int(reported.get("completion_tokens", 0)),
        )
        return str(content).strip(), usage

    async def aclose(self) -> None:
        await self._client.aclose()


class OllamaClient:
    provider = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.default_model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_url.rstrip("/"),
            timeout=httpx.Timeout(settings.llm_timeout_s, connect=10.0),
        )

    async def complete(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int
    ) -> tuple[str, Usage]:
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self._temperature, "num_predict": max_tokens},
        }
        try:
            response = await self._client.post("/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise UpstreamError("Ollama timed out.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("Ollama could not be reached.") from exc
        if response.status_code >= 400:
            raise UpstreamError(f"Ollama returned HTTP {response.status_code}.")
        payload = response.json()
        try:
            content = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise UpstreamError("Ollama returned an unexpected response.") from exc
        usage = Usage(
            prompt_tokens=int(payload.get("prompt_eval_count", 0)),
            completion_tokens=int(payload.get("eval_count", 0)),
        )
        return str(content).strip(), usage

    async def aclose(self) -> None:
        await self._client.aclose()


def build_chat_client(settings: Settings) -> ChatClient | None:
    """The configured model client, or None for the deterministic local providers."""
    if settings.llm_provider == "openai":
        return OpenAICompatibleClient(settings)
    if settings.llm_provider == "ollama":
        return OllamaClient(settings)
    return None
