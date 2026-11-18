"""Integration fixtures: real Postgres (pgvector), Valkey and the Floci AWS emulator.

`make test-integration` starts all three (scripts/test-deps.sh) and runs this suite. It
works in a database of its own (`graphrag_test`, recreated on every run), Valkey database 15
(flushed on every run) and uniquely named buckets, keys and queues on the emulator, so a
development stack's data is never touched. Point it elsewhere with TEST_DATABASE_ADMIN_URL,
TEST_REDIS_URL and TEST_AWS_ENDPOINT_URL.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import asyncpg
import boto3
import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.engine import URL, make_url

from graphrag.core.config import Settings
from graphrag.db.migrate import migrate
from graphrag.main import create_app
from graphrag.services.container import Container
from tests.integration.support import Account, import_notes, settle, signup

# The emulator accepts any credentials; real ones must never be sent to it.
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
for _name in ("AWS_SESSION_TOKEN", "AWS_PROFILE"):
    os.environ.pop(_name, None)

ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL", "postgresql://graphrag:graphrag@localhost:5460/graphrag"
)
REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6420/15")
AWS_ENDPOINT = os.environ.get("TEST_AWS_ENDPOINT_URL", "http://localhost:4620")
TEST_DATABASE = "graphrag_test"
WEB_ORIGIN = "http://localhost:3200"
RUN = uuid.uuid4().hex[:8]


def database_url(name: str) -> str:
    admin = make_url(ADMIN_URL)
    url = URL.create(
        "postgresql+asyncpg",
        username=admin.username,
        password=admin.password,
        host=admin.host,
        port=admin.port,
        database=name,
    )
    return url.render_as_string(hide_password=False)


async def recreate_database(name: str) -> None:
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def aws_client(service: str) -> Any:
    return boto3.client(service, endpoint_url=AWS_ENDPOINT, region_name="us-east-1")


@dataclass(frozen=True)
class AwsResources:
    bucket: str
    kms_key_id: str
    queue_url: str
    dlq_url: str


def provision_aws() -> AwsResources:
    """A KMS key, a documents bucket and a jobs queue with its dead-letter queue, like Terraform."""
    key_id = aws_client("kms").create_key(Description=f"graphrag integration {RUN}")["KeyMetadata"][
        "KeyId"
    ]
    bucket = f"graphrag-it-{RUN}"
    aws_client("s3").create_bucket(Bucket=bucket)
    sqs = aws_client("sqs")
    dlq_url = sqs.create_queue(QueueName=f"graphrag-it-{RUN}-dlq")["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    queue_url = sqs.create_queue(
        QueueName=f"graphrag-it-{RUN}",
        Attributes={
            "VisibilityTimeout": "60",
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"}),
        },
    )["QueueUrl"]
    return AwsResources(bucket, key_id, queue_url, dlq_url)


def make_settings(aws: AwsResources, **overrides: Any) -> Settings:
    """Test settings, independent of the developer's environment variables."""
    values: dict[str, Any] = {
        "app_env": "test",
        "log_level": "warning",
        "database_url": database_url(TEST_DATABASE),
        "redis_url": REDIS_URL,
        "session_secret": "integration-session-secret-0123456789abcdef",
        "api_key_pepper": "integration-api-key-pepper-0123456789abcdef",
        "cors_origins": [WEB_ORIGIN],
        "web_url": WEB_ORIGIN,
        "allow_signup": True,
        "storage_backend": "s3",
        "s3_bucket": aws.bucket,
        "s3_kms_key_id": aws.kms_key_id,
        "aws_endpoint_url": AWS_ENDPOINT,
        "aws_region": "us-east-1",
        "queue_backend": "inline",
        "sqs_queue_url": aws.queue_url,
        "url_fetch_allow_private": True,
        "rate_limit_query": 100_000,
        "rate_limit_login": 10_000,
        "rate_limit_ingest": 10_000,
        "rate_limit_build": 10_000,
    }
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.fixture(scope="session")
async def aws() -> AwsResources:
    return provision_aws()


@pytest.fixture(scope="session")
async def settings(aws: AwsResources) -> Settings:
    settings = make_settings(aws)
    await recreate_database(TEST_DATABASE)
    await migrate(settings)
    redis = Redis.from_url(REDIS_URL)
    await redis.flushdb()
    await redis.aclose()
    return settings


@pytest.fixture(scope="session")
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """The real application over ASGI: real database, cache, storage and inline jobs."""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as http:
            http.container = app.state.container  # type: ignore[attr-defined]
            yield http


def container_of(client: httpx.AsyncClient) -> Container:
    container: Container = client.container  # type: ignore[attr-defined]
    return container


@dataclass(frozen=True)
class Graph:
    """The demo notes ingested into one project: documents, graph and communities built."""

    owner: Account
    project: str

    @property
    def base(self) -> str:
        return f"/api/v1/projects/{self.project}"


@pytest.fixture(scope="session")
async def graph(client: httpx.AsyncClient) -> Graph:
    """The demo notes through the real pipeline, once for the whole session."""
    owner = await signup(client, "Graph Owner")
    await import_notes(client, owner, owner.project)
    await settle(client)
    return Graph(owner, owner.project)
