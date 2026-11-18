"""`make demo`: a lived-in project, built through the same services as any real use.

Meridian Research (fictional) keeps an analyst notebook on autonomous port logistics. The seed
creates three accounts, a project, uploads fourteen research notes, waits for the pipeline
(parse, embed, extract, resolve duplicates, detect communities, write reports) to finish
and then replays two weeks of questions through the real search service. Every chunk,
entity, relation, community report and answer is produced by the real pipeline; the only
liberty taken is time: the questions are spread over the past two weeks, so the dashboard has
a shape on a brand-new stack.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import anyio
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from graphrag.core.config import Settings
from graphrag.core.logging import get_logger
from graphrag.core.security import hash_password
from graphrag.demo.corpus import NOTES, QUESTIONS
from graphrag.integrations.queue import InlineQueue
from graphrag.models import Document, GraphBuild, QueryLog, User
from graphrag.models.enums import BuildStatus, JobStatus, Role
from graphrag.repositories.projects import ProjectRepository
from graphrag.repositories.users import UserRepository
from graphrag.schemas.documents import TextSource
from graphrag.schemas.search import QueryRequest
from graphrag.services.api_keys import ApiKeyService
from graphrag.services.container import Container, build_container
from graphrag.services.documents import DocumentService
from graphrag.services.ingestion import IngestionService
from graphrag.services.principal import Principal
from graphrag.services.projects import ProjectService
from graphrag.services.search import SearchService

log = get_logger("graphrag.demo")
PROJECT_SLUG = "port-intelligence"
PROJECT_NAME = "Port Intelligence"
PROJECT_DESCRIPTION = (
    "An analyst notebook on autonomous port logistics: who builds the vehicles, who funds and "
    "regulates them, and how batteries, sensors and digital twins fit together."
)


@dataclass(frozen=True)
class Person:
    email: str
    name: str
    role: Role
    admin: bool = False


PEOPLE = (
    Person("maya.iyer@meridian-research.example", "Maya Iyer", Role.OWNER, admin=True),
    Person("lucas.moreau@meridian-research.example", "Lucas Moreau", Role.EDITOR),
    Person("hana.takeda@meridian-research.example", "Hana Takeda", Role.VIEWER),
)


async def _person(container: Container, person: Person, password: str) -> User:
    async with container.db.session() as session:
        users = UserRepository(session)
        user = await users.by_email(person.email)
        if user is None:
            user = await users.add(
                User(
                    email=person.email,
                    name=person.name,
                    password_hash=await anyio.to_thread.run_sync(hash_password, password),
                    is_admin=person.admin,
                )
            )
            await session.commit()
        return user


async def _wait(container: Container, label: str, timeout_s: int = 900) -> None:
    """Until no document is unfinished and no build is queued or running."""
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        if isinstance(container.queue, InlineQueue):
            await container.queue.drain()
        async with container.db.session() as session:
            documents = await session.scalar(
                select(func.count()).where(
                    Document.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING])
                )
            )
            builds = await session.scalar(
                select(func.count()).where(
                    GraphBuild.status.in_([BuildStatus.QUEUED, BuildStatus.RUNNING])
                )
            )
        if not (documents or builds):
            return
        status = f"  {label}: {documents} document(s), {builds} build(s) unfinished"
        if status != last:
            print(status, flush=True)
            last = status
        await asyncio.sleep(2)
    raise TimeoutError(f"{label} did not finish in time; check `make logs SERVICE=worker`")


async def _seed(container: Container, password: str) -> tuple[str, str]:
    people = {p.email: await _person(container, p, password) for p in PEOPLE}
    maya, lucas, hana = (people[p.email] for p in PEOPLE)
    owner = Principal(user=maya)

    async with container.db.session() as session:
        project = await ProjectService(container, session).create(
            owner, PROJECT_NAME, PROJECT_DESCRIPTION
        )
        repo = ProjectRepository(session)
        await repo.add_member(project.id, lucas.id, Role.EDITOR)
        await repo.add_member(project.id, hana.id, Role.VIEWER)
        await session.commit()

    print(f"  uploading {len(NOTES)} research notes", flush=True)
    async with container.db.session() as session:
        outcome = await DocumentService(container, session).import_sources(
            project,
            Principal(user=lucas),
            [
                TextSource(
                    title=note.title,
                    text=note.body,
                    format="markdown",
                    external_id=note.slug,
                    metadata={"collection": "analyst-notes", "year": 2025},
                )
                for note in NOTES
            ],
        )
    print(f"  queued {len(outcome.created)} documents", flush=True)
    await _wait(container, "pipeline")

    async with container.db.session() as session:
        _, plaintext = await ApiKeyService(container, session).create(
            project, owner, "Analyst copilot", "viewer", None
        )
    return str(project.id), plaintext


async def _replay_traffic(container: Container, project_id: str) -> None:
    rng = random.Random(2026)
    plans: list[tuple[int, str, str]] = []
    for day in range(14):
        for _ in range(rng.randint(2, 6) + (3 if day in (2, 3, 9) else 0)):
            mode, question = rng.choice(QUESTIONS)
            plans.append((day, mode, question))
    print(f"  replaying {len(plans)} questions", flush=True)
    async with container.db.session() as session:
        project = await ProjectRepository(session).by_slug(PROJECT_SLUG)
        if project is None:
            return
        users = UserRepository(session)
        askers = [
            Principal(user=u)
            for u in [await users.by_email(p.email) for p in PEOPLE]
            if u is not None
        ]
        search = SearchService(container, session)
        for _, mode, question in plans:
            request = QueryRequest.model_validate(
                {"question": question, "mode": mode, "cache": False}
            )
            await search.ask(project, rng.choice(askers), request)
        now = datetime.now(UTC)
        rows = list(
            (
                await session.execute(
                    select(QueryLog.id)
                    .where(QueryLog.project_id == project.id)
                    .order_by(QueryLog.created_at)
                )
            ).scalars()
        )
        for log_id, (day, _, _) in zip(rows, plans, strict=False):
            when = now - timedelta(
                days=13 - day, hours=rng.uniform(0, 10), minutes=rng.uniform(0, 59)
            )
            await session.execute(
                update(QueryLog).where(QueryLog.id == log_id).values(created_at=when)
            )
        await session.commit()


async def run(settings: Settings, password: str, *, traffic: bool = True) -> None:
    container = build_container(settings)
    if isinstance(container.queue, InlineQueue):
        container.queue.bind(IngestionService(container).handle)
    try:
        async with container.db.session() as session:
            existing = await ProjectRepository(session).by_slug(PROJECT_SLUG)
        if existing is not None:
            print("The demo project already exists; nothing to seed.")
            _print_logins(settings, password, None)
            return
        project_id, key = await _seed(container, password)
        if traffic:
            await _replay_traffic(container, project_id)
        _print_logins(settings, password, key)
    finally:
        await container.close()


def _print_logins(settings: Settings, password: str, key: str | None) -> None:
    print("\nDemo ready. Sign in at", settings.web_url)
    for person in PEOPLE:
        print(f"  {person.email:<44} {person.role.value:<7} password: {password}")
    if key:
        print(f"\n  API key (viewer): {key}")
        print("\n  Try it:")
        print(f"  curl -s {settings.api_url}/api/v1/projects/{PROJECT_SLUG}/query \\")
        print(f"    -H 'authorization: Bearer {key}' -H 'content-type: application/json' \\")
        print('    -d \'{"question": "Who founded Helios Robotics?", "mode": "local"}\'')


async def rebuild(settings: Settings, project_slug: str) -> bool:
    """Queue a graph build for a project and, with the inline queue, wait for it."""
    container = build_container(settings)
    if isinstance(container.queue, InlineQueue):
        container.queue.bind(IngestionService(container).handle)
    try:
        async with container.db.session() as session:
            project = await ProjectRepository(session).by_slug(project_slug)
            if project is None:
                return False
            from graphrag.services.builds import BuildService

            await BuildService(container, session).request(
                project, Principal(user=await _any_owner(session, project.id))
            )
        if isinstance(container.queue, InlineQueue):
            await container.queue.drain()
        return True
    finally:
        await container.close()


async def _any_owner(session: AsyncSession, project_id: uuid.UUID) -> User | None:
    from graphrag.models import Membership

    row = await session.execute(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.project_id == project_id, Membership.role == Role.OWNER.value)
        .limit(1)
    )
    return row.scalar_one_or_none()
