"""Process-wide infrastructure, built once at startup and shared by every request.

Services are cheap objects created per request around one database session; everything
expensive (connection pools, HTTP clients, the model clients) lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from graphrag.ai.embeddings import EmbedderPool
from graphrag.ai.llm import ChatClient, build_chat_client
from graphrag.ai.tokens import TokenCounter
from graphrag.core.config import Settings
from graphrag.core.ratelimit import RateLimiter
from graphrag.db.session import Database
from graphrag.graph.extraction import build_extractor
from graphrag.graph.extraction.contracts import Extractor
from graphrag.graph.summaries import Reporter, build_reporter
from graphrag.integrations.fetcher import UrlFetcher
from graphrag.integrations.queue import InlineQueue, SqsQueue, build_queue
from graphrag.integrations.storage import Storage, build_storage


@dataclass
class Container:
    settings: Settings
    db: Database
    redis: Redis
    storage: Storage
    queue: InlineQueue | SqsQueue
    fetcher: UrlFetcher
    tokens: TokenCounter
    embedders: EmbedderPool
    chat_client: ChatClient | None
    extractor: Extractor
    reporter: Reporter
    limiter: RateLimiter

    async def close(self) -> None:
        if self.chat_client is not None:
            await self.chat_client.aclose()
        await self.embedders.aclose()
        await self.fetcher.aclose()
        await self.redis.aclose()
        await self.db.dispose()


def build_container(settings: Settings) -> Container:
    redis = Redis.from_url(
        settings.redis_url, decode_responses=False, health_check_interval=30, socket_timeout=5
    )
    chat_client = build_chat_client(settings)
    return Container(
        settings=settings,
        db=Database(settings),
        redis=redis,
        storage=build_storage(settings),
        queue=build_queue(settings),
        fetcher=UrlFetcher(settings),
        tokens=TokenCounter(settings.tokenizer),
        embedders=EmbedderPool(settings, redis),
        chat_client=chat_client,
        extractor=build_extractor(chat_client, settings.llm_max_tokens),
        reporter=build_reporter(chat_client, settings.llm_max_tokens),
        limiter=RateLimiter(redis),
    )
