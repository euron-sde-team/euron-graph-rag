import fakeredis
import httpx
import numpy as np
import pytest
import respx

from graphrag.ai.embeddings import (
    CachedEmbedder,
    EmbedderPool,
    HashEmbedder,
    OllamaEmbedder,
    OpenAIEmbedder,
    spec_from_settings,
)
from graphrag.core.config import Settings
from graphrag.core.errors import UpstreamError

SPEC = spec_from_settings(Settings())


async def test_hash_vectors_are_deterministic_unit_length_and_lexically_similar() -> None:
    embedder = HashEmbedder(SPEC)
    a, b, c = await embedder.embed_documents(
        [
            "Helios Robotics builds autonomous vehicles for container terminals.",
            "Autonomous vehicles for container terminals are built by Helios Robotics.",
            "Voltaic Cells makes solid-state batteries in Austin.",
        ]
    )
    again = await embedder.embed_query(
        "Helios Robotics builds autonomous vehicles for container terminals."
    )
    assert np.allclose(a, again)
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-5
    assert float(a @ b) > float(a @ c) + 0.3
    assert a.shape == (384,)


async def test_empty_input_yields_an_empty_matrix() -> None:
    assert (await HashEmbedder(SPEC).embed_documents([])).shape == (0, 384)


def test_settings_choose_the_provider_model_and_width() -> None:
    assert spec_from_settings(Settings()).key == "local:hashing:384"
    spec = spec_from_settings(
        Settings(embedding_provider="ollama", embedding_model="nomic-embed-text", embedding_dim=768)
    )
    assert (spec.provider, spec.model, spec.dim) == ("ollama", "nomic-embed-text", 768)


@respx.mock
async def test_the_openai_adapter_orders_rows_checks_the_width_and_sends_dimensions() -> None:
    spec = spec_from_settings(
        Settings(
            embedding_provider="openai", embedding_model="text-embedding-3-small", embedding_dim=768
        )
    )
    route = respx.post("https://api.test/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 2.0] + [0.0] * 766},
                    {"index": 0, "embedding": [3.0, 0.0] + [0.0] * 766},
                ]
            },
        )
    )
    embedder = OpenAIEmbedder(spec, "https://api.test/v1", "sk-test")
    matrix = await embedder.embed_documents(["first", "second"])
    assert matrix[0][0] == pytest.approx(1.0) and matrix[1][1] == pytest.approx(1.0)
    sent = route.calls[0].request
    assert b'"dimensions":768' in sent.content.replace(b" ", b"")
    assert sent.headers["authorization"] == "Bearer sk-test"
    respx.post("https://api.test/v1/embeddings").mock(
        return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]})
    )
    with pytest.raises(UpstreamError, match="dimensions"):
        await embedder.embed_documents(["short"])
    await embedder.aclose()


@respx.mock
async def test_the_ollama_adapter_reports_failures_as_upstream_errors() -> None:
    spec = spec_from_settings(
        Settings(embedding_provider="ollama", embedding_model="nomic-embed-text", embedding_dim=768)
    )
    respx.post("http://ollama.test/api/embed").mock(return_value=httpx.Response(500))
    embedder = OllamaEmbedder(spec, "http://ollama.test")
    with pytest.raises(UpstreamError):
        await embedder.embed_documents(["x"])
    respx.post("http://ollama.test/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[1.0] + [0.0] * 767]})
    )
    assert (await embedder.embed_query("x")).shape == (768,)
    await embedder.aclose()


class CountingEmbedder(HashEmbedder):
    calls = 0

    async def embed_documents(self, texts):  # type: ignore[no-untyped-def]
        type(self).calls += len(texts)
        return await super().embed_documents(texts)


async def test_the_cache_serves_repeated_text_and_isolates_projects() -> None:
    redis = fakeredis.FakeAsyncRedis()
    inner = CountingEmbedder(SPEC)
    one = CachedEmbedder(inner, redis, 60, "project-one")
    first = await one.embed_documents(["alpha beta", "gamma"])
    assert CountingEmbedder.calls == 2
    again = await one.embed_documents(["alpha beta", "gamma", "delta"])
    assert CountingEmbedder.calls == 3
    assert np.allclose(first, again[:2])
    await CachedEmbedder(inner, redis, 60, "project-two").embed_documents(["alpha beta"])
    assert CountingEmbedder.calls == 4, "another project never reads this project's cache"


async def test_the_pool_serves_the_configured_model_per_project() -> None:
    pool = EmbedderPool(Settings(), fakeredis.FakeAsyncRedis())
    assert pool.spec.dim == 384
    vector = await pool.get("p1").embed_query("hello world")
    assert vector.shape == (384,)
    await pool.aclose()
