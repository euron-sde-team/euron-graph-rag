"""The job queue: SQS (with a dead-letter queue) in deployments, in-process otherwise.

Three kinds of job share one queue (see `Job`). Delivery is at least once, so every handler
is idempotent.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol

import anyio
import orjson

from graphrag.core.config import Settings
from graphrag.core.logging import get_logger
from graphrag.integrations import aws

log = get_logger("graphrag.queue")

JobKind = Literal["parse", "extract", "build"]


@dataclass(frozen=True, slots=True)
class Job:
    """Three kinds of job share one queue: parse and embed a document, extract its entities
    and relations, and build the project's communities. Messages carry ids only; every
    handler re-reads its rows and is idempotent, so a duplicated or stale message is
    harmless."""

    kind: JobKind
    project_id: uuid.UUID
    document_id: uuid.UUID | None = None
    build_id: uuid.UUID | None = None

    @classmethod
    def parse(cls, project_id: uuid.UUID, document_id: uuid.UUID) -> Job:
        return cls("parse", project_id, document_id=document_id)

    @classmethod
    def extract(cls, project_id: uuid.UUID, document_id: uuid.UUID) -> Job:
        return cls("extract", project_id, document_id=document_id)

    @classmethod
    def build(cls, project_id: uuid.UUID, build_id: uuid.UUID) -> Job:
        return cls("build", project_id, build_id=build_id)

    def encode(self) -> str:
        body: dict[str, str] = {"kind": self.kind, "project_id": str(self.project_id)}
        for name in ("document_id", "build_id"):
            value = getattr(self, name)
            if value is not None:
                body[name] = str(value)
        return orjson.dumps(body).decode()

    @classmethod
    def decode(cls, body: str) -> Job:
        data = orjson.loads(body)
        kind = data["kind"]
        if kind not in ("parse", "extract", "build"):
            raise ValueError(f"unknown job kind {kind!r}")

        def optional(name: str) -> uuid.UUID | None:
            return uuid.UUID(data[name]) if data.get(name) else None

        job = cls(
            kind,
            uuid.UUID(data["project_id"]),
            document_id=optional("document_id"),
            build_id=optional("build_id"),
        )
        required = "build_id" if kind == "build" else "document_id"
        if getattr(job, required) is None:
            raise ValueError(f"{kind} job is missing {required}")
        return job

    @property
    def subject(self) -> str:
        """The id a log line or a metric should name."""
        return str(self.build_id or self.document_id)


@dataclass(frozen=True, slots=True)
class ReceivedJob:
    job: Job
    receipt: str
    receive_count: int


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> None: ...

    async def backlog(self) -> int: ...

    async def check(self) -> None: ...


Handler = Callable[[Job], Awaitable[object]]


class InlineQueue:
    """Runs jobs as background tasks in the API process. Development and tests.

    Jobs run one at a time, in the order they were enqueued, which mirrors a single worker
    and keeps a graph build from racing the extraction it depends on.
    """

    def __init__(self) -> None:
        self._handler: Handler | None = None
        self._pending: asyncio.Queue[Job] = asyncio.Queue()
        self._runner: asyncio.Task[None] | None = None
        self._busy = 0

    def bind(self, handler: Handler) -> None:
        self._handler = handler

    async def enqueue(self, job: Job) -> None:
        if self._handler is None:
            raise RuntimeError("InlineQueue has no handler bound")
        self._busy += 1
        await self._pending.put(job)
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while not self._pending.empty():
            job = await self._pending.get()
            try:
                if self._handler is not None:
                    await self._handler(job)
            except Exception:
                log.exception("inline_job_failed", kind=job.kind, subject=job.subject)
            finally:
                self._busy -= 1

    async def drain(self) -> None:
        """Wait until every enqueued job, including jobs enqueued by jobs, has finished."""
        while self._busy or (self._runner is not None and not self._runner.done()):
            if self._runner is not None and not self._runner.done():
                await asyncio.shield(self._runner)
            elif self._busy:
                self._runner = asyncio.create_task(self._run())

    async def backlog(self) -> int:
        return self._busy

    async def check(self) -> None:
        return None


class SqsQueue:
    def __init__(self, settings: Settings) -> None:
        if not settings.sqs_queue_url:
            raise ValueError("SQS_QUEUE_URL is required for QUEUE_BACKEND=sqs")
        self.url = settings.sqs_queue_url
        self._client = aws.sqs_client(settings)

    async def enqueue(self, job: Job) -> None:
        await anyio.to_thread.run_sync(
            lambda: self._client.send_message(QueueUrl=self.url, MessageBody=job.encode())
        )

    async def receive(
        self, *, max_messages: int, wait_s: int, visibility_s: int
    ) -> list[ReceivedJob]:
        response = await anyio.to_thread.run_sync(
            lambda: self._client.receive_message(
                QueueUrl=self.url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_s,
                VisibilityTimeout=visibility_s,
                MessageSystemAttributeNames=["ApproximateReceiveCount"],
            )
        )
        received = []
        for message in response.get("Messages", []):
            try:
                job = Job.decode(message["Body"])
            except (ValueError, KeyError, TypeError):
                log.warning("queue_message_malformed", message_id=message.get("MessageId"))
                await self.delete(message["ReceiptHandle"])
                continue
            count = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
            received.append(ReceivedJob(job, message["ReceiptHandle"], count))
        return received

    async def delete(self, receipt: str) -> None:
        await anyio.to_thread.run_sync(
            lambda: self._client.delete_message(QueueUrl=self.url, ReceiptHandle=receipt)
        )

    async def extend(self, receipt: str, visibility_s: int) -> None:
        await anyio.to_thread.run_sync(
            lambda: self._client.change_message_visibility(
                QueueUrl=self.url, ReceiptHandle=receipt, VisibilityTimeout=visibility_s
            )
        )

    async def backlog(self) -> int:
        """Messages waiting to be received (approximate, as SQS reports it)."""
        response = await anyio.to_thread.run_sync(
            lambda: self._client.get_queue_attributes(
                QueueUrl=self.url, AttributeNames=["ApproximateNumberOfMessages"]
            )
        )
        return int(response.get("Attributes", {}).get("ApproximateNumberOfMessages", "0"))

    async def check(self) -> None:
        await self.backlog()


def build_queue(settings: Settings) -> InlineQueue | SqsQueue:
    if settings.queue_backend == "sqs":
        return SqsQueue(settings)
    return InlineQueue()
