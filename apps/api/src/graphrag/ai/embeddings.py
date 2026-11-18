"""Embedding models behind one interface: three providers and a shared cache.

| Provider | Runs | Use |
| local    | signed feature hashing of words and word pairs, no model | default, tests, demo |
| openai   | any OpenAI-compatible /embeddings endpoint | hosted |
| ollama   | an Ollama server (/api/embed) | local GPU or CPU |

Every vector is L2-normalised, so cosine similarity is a dot product everywhere. The width is
a deployment setting (EMBEDDING_DIM) and must be one with an HNSW index.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Protocol

import httpx
import numpy as np
from redis.asyncio import Redis

from graphrag.core import metrics
from graphrag.core.config import Settings
from graphrag.core.errors import UpstreamError
from graphrag.core.logging import get_logger
from graphrag.core.text import content_terms

log = get_logger("graphrag.embeddings")
Matrix = np.ndarray[Any, np.dtype[np.float32]]


@dataclass(frozen=True, slots=True)
class EmbeddingSpec:
    provider: str
    model: str
    dim: int

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}:{self.dim}"

    def public(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "dim": self.dim}


def spec_from_settings(settings: Settings) -> EmbeddingSpec:
    if settings.embedding_provider == "local":
        return EmbeddingSpec("local", "hashing", settings.embedding_dim)
    return EmbeddingSpec(
        settings.embedding_provider, settings.embedding_model, settings.embedding_dim
    )


def first_row(matrix: Matrix) -> Matrix:
    row: Matrix = matrix[0]
    return row


def normalize_rows(matrix: Matrix) -> Matrix:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized: Matrix = (matrix / norms).astype(np.float32)
    return normalized


class Embedder(Protocol):
    spec: EmbeddingSpec

    async def embed_documents(self, texts: Sequence[str]) -> Matrix: ...

    async def embed_query(self, text: str) -> Matrix: ...


class HashEmbedder:
    """Signed feature hashing of stemmed words and word pairs: lexical, instant, offline."""

    def __init__(self, spec: EmbeddingSpec) -> None:
        self.spec = spec

    def _vector(self, text: str) -> Matrix:
        terms = content_terms(text)
        features = Counter(terms)
        features.update({f"{a} {b}": 0.5 for a, b in pairwise(terms)})
        vector = np.zeros(self.spec.dim, dtype=np.float32)
        for feature, weight in features.items():
            digest = int.from_bytes(
                hashlib.blake2b(feature.encode(), digest_size=8).digest(), "little"
            )
            sign = 1.0 if digest >> 63 else -1.0
            vector[digest % self.spec.dim] += (
                sign * (1 + math.log(weight)) if weight >= 1 else sign * weight
            )
        return vector

    async def embed_documents(self, texts: Sequence[str]) -> Matrix:
        if not texts:
            return np.zeros((0, self.spec.dim), dtype=np.float32)
        return normalize_rows(np.stack([self._vector(t) for t in texts]).astype(np.float32))

    async def embed_query(self, text: str) -> Matrix:
        return first_row(await self.embed_documents([text]))


class OpenAIEmbedder:
    def __init__(self, spec: EmbeddingSpec, base_url: str, api_key: str | None) -> None:
        self.spec = spec
        headers = {"authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=60.0
        )

    async def embed_documents(self, texts: Sequence[str]) -> Matrix:
        if not texts:
            return np.zeros((0, self.spec.dim), dtype=np.float32)
        body: dict[str, Any] = {"model": self.spec.model, "input": list(texts)}
        # Only the text-embedding-3 family accepts a width; other servers may reject it.
        if self.spec.model.startswith("text-embedding-3"):
            body["dimensions"] = self.spec.dim
        try:
            response = await self._client.post("/embeddings", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamError("The embedding provider request failed.") from exc
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        matrix = np.asarray([item["embedding"] for item in data], dtype=np.float32)
        if matrix.shape[1] != self.spec.dim:
            raise UpstreamError(
                f"{self.spec.model} returned {matrix.shape[1]} dimensions, not {self.spec.dim}."
            )
        return normalize_rows(matrix)

    async def embed_query(self, text: str) -> Matrix:
        return first_row(await self.embed_documents([text]))

    async def aclose(self) -> None:
        await self._client.aclose()


class OllamaEmbedder:
    def __init__(self, spec: EmbeddingSpec, url: str) -> None:
        self.spec = spec
        self._client = httpx.AsyncClient(base_url=url.rstrip("/"), timeout=60.0)

    async def embed_documents(self, texts: Sequence[str]) -> Matrix:
        if not texts:
            return np.zeros((0, self.spec.dim), dtype=np.float32)
        try:
            response = await self._client.post(
                "/api/embed", json={"model": self.spec.model, "input": list(texts)}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamError("The Ollama embedding request failed.") from exc
        matrix = np.asarray(response.json()["embeddings"], dtype=np.float32)
        if matrix.shape[1] != self.spec.dim:
            raise UpstreamError(
                f"{self.spec.model} returned {matrix.shape[1]} dimensions, not {self.spec.dim}."
            )
        return normalize_rows(matrix)

    async def embed_query(self, text: str) -> Matrix:
        return first_row(await self.embed_documents([text]))

    async def aclose(self) -> None:
        await self._client.aclose()


class CachedEmbedder:
    """Read-through Redis cache keyed by project, model, width and the SHA-256 of the text.

    Re-extracting unchanged text, rebuilding communities or asking a popular question again
    costs one Redis round trip instead of a model call. The project is part of the key so one
    project's traffic can never reveal, even through timing, what another has embedded.
    """

    def __init__(self, inner: Embedder, redis: Redis, ttl_s: int, scope: str) -> None:
        self.inner = inner
        self.spec = inner.spec
        self._redis = redis
        self._ttl = ttl_s
        self._scope = scope

    def _key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode()).hexdigest()
        return f"emb:{self._scope}:{self.spec.key}:{digest}"

    async def embed_documents(self, texts: Sequence[str]) -> Matrix:
        if not texts:
            return np.zeros((0, self.spec.dim), dtype=np.float32)
        keys = [self._key(t) for t in texts]
        try:
            stored = await self._redis.mget(keys)
        except Exception:
            stored = [None] * len(texts)
        result = np.zeros((len(texts), self.spec.dim), dtype=np.float32)
        missing = [i for i, raw in enumerate(stored) if raw is None]
        for i, raw in enumerate(stored):
            if raw is not None:
                buffer = raw.encode("latin-1") if isinstance(raw, str) else raw
                result[i] = np.frombuffer(buffer, dtype=np.float32)
        metrics.CACHE.labels("embedding", "hit").inc(len(texts) - len(missing))
        metrics.CACHE.labels("embedding", "miss").inc(len(missing))
        if missing:
            fresh = await self.inner.embed_documents([texts[i] for i in missing])
            for row, i in enumerate(missing):
                result[i] = fresh[row]
            try:
                async with self._redis.pipeline(transaction=False) as pipe:
                    for row, i in enumerate(missing):
                        pipe.set(keys[i], fresh[row].tobytes(), ex=self._ttl or None)
                    await pipe.execute()
            except Exception:
                log.warning("embedding_cache_write_failed")
        return result

    async def embed_query(self, text: str) -> Matrix:
        return first_row(await self.embed_documents([text]))


class EmbedderPool:
    """The deployment's embedding model, created once, behind a per-project Redis cache."""

    def __init__(self, settings: Settings, redis: Redis) -> None:
        self._settings = settings
        self._redis = redis
        self.spec = spec_from_settings(settings)
        self._closers: list[Any] = []
        self._model = self._build()

    def _build(self) -> Embedder:
        settings = self._settings
        match self.spec.provider:
            case "openai":
                key = settings.embeddings_api_key
                openai = OpenAIEmbedder(
                    self.spec, settings.embeddings_api_base, key.get_secret_value() if key else None
                )
                self._closers.append(openai.aclose)
                return openai
            case "ollama":
                ollama = OllamaEmbedder(self.spec, settings.ollama_url)
                self._closers.append(ollama.aclose)
                return ollama
            case _:
                return HashEmbedder(self.spec)

    def get(self, scope: str) -> CachedEmbedder:
        """The model, cached under `scope` (a project id)."""
        return CachedEmbedder(self._model, self._redis, self._settings.embedding_cache_ttl_s, scope)

    async def aclose(self) -> None:
        for closer in self._closers:
            await closer()
