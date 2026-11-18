"""The job worker on the emulator's SQS: parse, extract and build jobs, and the reaper."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update

from graphrag.core.config import Settings
from graphrag.integrations.queue import Job, SqsQueue
from graphrag.models import Document, GraphBuild, Project, User
from graphrag.models.enums import BuildStatus, JobStatus
from graphrag.schemas.documents import TextSource
from graphrag.services.container import Container, build_container
from graphrag.services.documents import DocumentService
from graphrag.services.ingestion import IngestionService
from graphrag.services.principal import Principal
from graphrag.worker import Worker
from tests.integration.conftest import AwsResources, aws_client
from tests.integration.support import signup

pytestmark = pytest.mark.integration

NOTE = (
    "Orion Labs partnered with Nova Systems in 2024. Dr. Ana Duarte founded Orion Labs in 2019. "
    "Nova Systems is based in Madrid."
)


@pytest.fixture(scope="module")
async def sqs(settings: Settings) -> AsyncIterator[Container]:
    """A worker-side container: same database, storage and cache, jobs through SQS."""
    container = build_container(settings.model_copy(update={"queue_backend": "sqs"}))
    yield container
    await container.close()


@pytest.fixture
async def target(client: httpx.AsyncClient, sqs: Container) -> tuple[Principal, Project]:
    account = await signup(client, "Worker Owner")
    async with sqs.db.session() as session:
        user = await session.get(User, uuid.UUID(account.user_id))
        project = (
            await session.execute(select(Project).where(Project.slug == account.project))
        ).scalar_one()
    assert user is not None
    return Principal(user=user), project


def depth(queue_url: str) -> tuple[int, int]:
    """(waiting, in flight) messages."""
    attributes = aws_client("sqs").get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    return int(attributes["ApproximateNumberOfMessages"]), int(
        attributes["ApproximateNumberOfMessagesNotVisible"]
    )


def lose_messages(queue_url: str) -> None:
    sqs = aws_client("sqs")
    while messages := sqs.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1
    ).get("Messages"):
        for message in messages:
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])


async def work_until(
    sqs: Container, finished: Callable[[], Awaitable[bool]], timeout_s: float = 120
) -> None:
    """Run a real worker until `finished`, then stop it the way SIGTERM does."""
    assert isinstance(sqs.queue, SqsQueue)
    worker = Worker(sqs, sqs.queue)
    running = asyncio.create_task(worker.run())
    try:
        deadline = time.monotonic() + timeout_s
        while not await finished():
            assert not running.done(), "the worker stopped on its own"
            assert time.monotonic() < deadline, "the worker did not finish in time"
            await asyncio.sleep(0.5)
    finally:
        worker.stop()
        await asyncio.wait_for(running, timeout=60)


async def add_note(sqs: Container, target: tuple[Principal, Project], name: str) -> uuid.UUID:
    principal, project = target
    async with sqs.db.session() as session:
        outcome = await DocumentService(sqs, session).import_sources(
            project, principal, [TextSource(title=name, text=f"{NOTE} {name}.", external_id=name)]
        )
    assert outcome.created, outcome.rejected
    return outcome.created[0].id


def build_done(sqs: Container, project: Project) -> Callable[[], Awaitable[bool]]:
    async def check() -> bool:
        async with sqs.db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(GraphBuild.status).where(GraphBuild.project_id == project.id)
                    )
                )
                .scalars()
                .all()
            )
        return bool(rows) and all(s in (BuildStatus.COMPLETED, BuildStatus.FAILED) for s in rows)

    return check


async def test_a_worker_takes_a_document_from_upload_to_a_built_graph(
    sqs: Container, target: tuple[Principal, Project], aws: AwsResources
) -> None:
    document_id = await add_note(sqs, target, "queued-note")
    await work_until(sqs, build_done(sqs, target[1]))
    async with sqs.db.session() as session:
        document = await session.get(Document, document_id)
        build = (
            await session.execute(select(GraphBuild).where(GraphBuild.project_id == target[1].id))
        ).scalar_one()
    assert document is not None
    assert (document.status, document.stage) == (JobStatus.READY, "done")
    assert document.entity_count >= 3 and document.relation_count >= 2
    assert build.status == BuildStatus.COMPLETED and build.stats["entities"] >= 3
    waiting, in_flight = depth(aws.queue_url)
    assert waiting == 0 and in_flight == 0, "every message was deleted after its job finished"


async def test_a_lost_message_is_found_again_by_the_reaper(
    sqs: Container, target: tuple[Principal, Project], aws: AwsResources
) -> None:
    document_id = await add_note(sqs, target, "lost-note")
    lose_messages(aws.queue_url)
    async with sqs.db.session() as session:
        await session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(updated_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()
    assert await IngestionService(sqs).reap_stale() == 1
    await work_until(sqs, build_done(sqs, target[1]))
    async with sqs.db.session() as session:
        document = await session.get(Document, document_id)
    assert document is not None and document.status == JobStatus.READY


async def test_a_duplicate_delivery_of_finished_work_is_a_no_op(
    sqs: Container, target: tuple[Principal, Project]
) -> None:
    document_id = await add_note(sqs, target, "twice-note")
    await work_until(sqs, build_done(sqs, target[1]))
    service = IngestionService(sqs)
    async with sqs.db.session() as session:
        before = await session.get(Document, document_id)
        assert before is not None
        extracted = before.extracted_at
    await service.handle(Job.parse(target[1].id, document_id))
    await service.handle(Job.extract(target[1].id, document_id))
    async with sqs.db.session() as session:
        after = await session.get(Document, document_id)
    assert after is not None and after.extracted_at == extracted


async def test_a_document_without_text_fails_with_a_readable_reason(
    sqs: Container, target: tuple[Principal, Project]
) -> None:
    principal, project = target
    async with sqs.db.session() as session:
        outcome = await DocumentService(sqs, session).import_sources(
            project, principal, [TextSource(title="Blank", text="   \n\n   ", external_id="blank")]
        )
    document_id = outcome.created[0].id

    async def failed() -> bool:
        async with sqs.db.session() as session:
            document = await session.get(Document, document_id)
        return document is not None and document.status == JobStatus.FAILED

    await work_until(sqs, failed)
    async with sqs.db.session() as session:
        document = await session.get(Document, document_id)
    assert document is not None and "no text" in (document.error or "")
