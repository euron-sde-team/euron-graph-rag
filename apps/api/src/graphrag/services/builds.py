"""Graph builds: duplicate resolution, community detection, hierarchical reports.

A build reads the whole graph of a project and replaces its communities in one transaction.
Work that arrives while a build waits coalesces into it (one queued build per project at a
time), and a build that finds documents still extracting waits for them, so a batch of
uploads is summarized once.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from graphrag.core import metrics
from graphrag.core.errors import AppError, ConflictError
from graphrag.core.ids import uuid7
from graphrag.core.logging import get_logger
from graphrag.graph.communities import (
    CommunityNode,
    build_hierarchy,
    modularity,
)
from graphrag.graph.resolution import Candidate, find_duplicates
from graphrag.graph.summaries import (
    ChildBrief,
    EntityBrief,
    RelationBrief,
    Report,
    ReportInput,
)
from graphrag.integrations.queue import InlineQueue, Job
from graphrag.models import Entity, GraphBuild, Project, Relation
from graphrag.models.enums import BuildStatus, JobStatus
from graphrag.repositories.communities import BuildRepository, CommunityRepository, CommunityRow
from graphrag.repositories.documents import DocumentRepository
from graphrag.repositories.graph import GraphRepository
from graphrag.schemas.projects import GraphSettings
from graphrag.services import audit
from graphrag.services.container import Container
from graphrag.services.principal import Principal

log = get_logger("graphrag.builds")
MAX_ATTEMPTS = 3
WAIT_FOR_DOCUMENTS_S = 120
REPORT_CONCURRENCY = 4
EVIDENCE_PER_RELATION = 3


class Outcome(StrEnum):
    DONE = "done"
    RETRY = "retry"


def project_settings(project: Project) -> GraphSettings:
    return GraphSettings.model_validate(project.settings or {})


class BuildService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.builds = BuildRepository(session)
        self._to_dispatch: list[GraphBuild] = []

    # Requesting -------------------------------------------------------------------------

    async def graph_changed(
        self, project: Project, user_id: uuid.UUID | None = None, *, trigger: str = "auto"
    ) -> None:
        """The graph's content changed: retire cached answers and, when the project builds
        automatically, make sure a build is queued."""
        project.graph_version += 1
        if trigger == "auto" and not project_settings(project).auto_build:
            return
        await self._ensure_queued(project, trigger, user_id)

    async def _ensure_queued(
        self, project: Project, trigger: str, user_id: uuid.UUID | None
    ) -> GraphBuild:
        pending = await self.builds.pending(project.id)
        if pending is not None:
            return pending
        settings = project_settings(project)
        build = await self.builds.add(
            GraphBuild(
                id=uuid7(),
                project_id=project.id,
                status=BuildStatus.QUEUED,
                trigger=trigger,
                params={
                    "levels": settings.community_levels,
                    "resolution": settings.resolution,
                    "extractor": self.c.extractor.name,
                    "reporter": self.c.reporter.name,
                },
                stats={},
                created_by=user_id,
            )
        )
        self._to_dispatch.append(build)
        return build

    async def request(self, project: Project, principal: Principal) -> GraphBuild:
        """A manual rebuild. Refuses while one is already waiting, which will include the
        caller's changes anyway."""
        if await self.builds.pending(project.id) is not None:
            raise ConflictError("A build is already queued; it will include your changes.")
        build = await self._ensure_queued(project, "manual", principal.user_id)
        project.graph_version += 1
        await audit.record(
            self.session,
            project_id=project.id,
            principal=principal,
            action="build.requested",
            target_type="build",
            target_id=build.id,
        )
        await self.session.commit()
        await self.dispatch_pending(project)
        return build

    async def dispatch_pending(self, project: Project) -> None:
        """Queue the jobs of builds created in this unit of work; call after the commit."""
        pending, self._to_dispatch = self._to_dispatch, []
        for build in pending:
            await self.c.queue.enqueue(Job.build(project.id, build.id))

    # Running ----------------------------------------------------------------------------

    async def execute(self, build_id: uuid.UUID, *, final_attempt: bool) -> Outcome:
        async with self.c.db.session() as session:
            row = await BuildRepository(session).get_for_update(build_id)
            if row is None or row.status in (BuildStatus.COMPLETED, BuildStatus.FAILED):
                return Outcome.DONE
            project = await session.get(Project, row.project_id)
            if project is None:
                return Outcome.DONE
            row.status = BuildStatus.RUNNING
            row.attempts += 1
            row.started_at = datetime.now(UTC)
            row.error = None
            settings = project_settings(project)
            project_id = project.id
            await session.commit()

        started = time.perf_counter()
        try:
            await self._wait_for_documents(project_id)
            stats = await self._run(project_id, build_id, settings)
        except Exception as exc:
            log.exception("build_error", build_id=str(build_id))
            retry = not final_attempt and not isinstance(exc, AppError)
            await self._finish(
                build_id,
                BuildStatus.QUEUED if retry else BuildStatus.FAILED,
                error=None if retry else _message(exc),
            )
            metrics.BUILDS.labels("retry" if retry else "failed").inc()
            return Outcome.RETRY if retry else Outcome.DONE
        elapsed = time.perf_counter() - started
        await self._finish(
            build_id, BuildStatus.COMPLETED, stats={**stats, "seconds": round(elapsed, 2)}
        )
        metrics.BUILDS.labels("completed").inc()
        metrics.BUILD_DURATION.observe(elapsed)
        log.info("graph_built", build_id=str(build_id), seconds=round(elapsed, 2), **stats)
        return Outcome.DONE

    async def _wait_for_documents(self, project_id: uuid.UUID) -> None:
        if isinstance(self.c.queue, InlineQueue):
            return
        waited = 0
        while waited < WAIT_FOR_DOCUMENTS_S:
            async with self.c.db.session() as session:
                counts = await DocumentRepository(session).status_counts(project_id)
            if not counts.get(JobStatus.QUEUED, 0) + counts.get(JobStatus.PROCESSING, 0):
                return
            await asyncio.sleep(2)
            waited += 2

    async def _finish(
        self,
        build_id: uuid.UUID,
        status: BuildStatus,
        *,
        stats: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        async with self.c.db.session() as session:
            row = await BuildRepository(session).get_for_update(build_id)
            if row is None:
                return
            row.status = status
            row.error = error
            if status in (BuildStatus.COMPLETED, BuildStatus.FAILED):
                row.finished_at = datetime.now(UTC)
            if stats is not None:
                row.stats = stats
            await session.commit()

    async def _run(
        self, project_id: uuid.UUID, build_id: uuid.UUID, settings: GraphSettings
    ) -> dict[str, Any]:
        merges = await self._resolve_duplicates(project_id)
        embedder = self.c.embedders.get(str(project_id))
        dim = self.c.embedders.spec.dim

        async with self.c.db.session() as session:
            graph = GraphRepository(session)
            entities = {e.id: e for e in await graph.all_entities(project_id)}
            relations = await graph.all_relations(project_id)
            evidence = await graph.evidence_for(project_id, [r.id for r in relations])
        chunk_ids_by_relation: dict[uuid.UUID, list[str]] = defaultdict(list)
        for item in evidence:
            if len(chunk_ids_by_relation[item.relation_id]) < EVIDENCE_PER_RELATION:
                chunk_ids_by_relation[item.relation_id].append(str(item.chunk_id))

        edges = [(str(r.source_id), str(r.target_id), r.weight) for r in relations]
        node_ids = [str(i) for i in entities]
        levels = build_hierarchy(
            node_ids,
            edges,
            max_levels=settings.community_levels,
            resolution=settings.resolution,
        )
        top = [node.members for node in levels[0]] if levels else []
        score = modularity(top, edges) if top else 0.0

        reports = await self._write_reports(levels, entities, relations, chunk_ids_by_relation)
        order = list(reports)
        vectors = (
            await embedder.embed_documents(
                [f"{reports[ref][0].title}. {reports[ref][0].summary}" for ref in order]
            )
            if order
            else np.zeros((0, dim), dtype=np.float32)
        )
        ids = {ref: uuid7() for ref in order}
        rows: list[CommunityRow] = []
        for position, ref in enumerate(order):
            node = _node(levels, ref)
            report = reports[ref][0]
            members = [uuid.UUID(m) for m in sorted(node.members)]
            inside = [
                r
                for r in relations
                if str(r.source_id) in node.members and str(r.target_id) in node.members
            ]
            rows.append(
                CommunityRow(
                    id=ids[ref],
                    parent_id=ids.get(node.parent) if node.parent else None,
                    level=node.level,
                    ordinal=node.ordinal,
                    title=report.title,
                    summary=report.summary,
                    findings=[f.as_dict() for f in report.findings],
                    entity_count=len(members),
                    relation_count=len(inside),
                    rank=round(sum(entities[m].importance for m in members), 4),
                    reporter=reports[ref][1],
                    embedding=vectors[position],
                    members=members,
                )
            )
        async with self.c.db.session() as session:
            await CommunityRepository(session).replace_all(project_id, build_id, rows, dim)
            project = await session.get(Project, project_id)
            if project is not None:
                project.graph_version += 1
            await session.commit()
        return {
            "entities": len(entities),
            "relations": len(relations),
            "merged": merges,
            "communities": len(rows),
            "levels": [len(level) for level in levels],
            "modularity": round(score, 4),
            "isolated": len(entities) - len({m for r in rows if r.level == 0 for m in r.members}),
        }

    async def _resolve_duplicates(self, project_id: uuid.UUID) -> int:
        async with self.c.db.session() as session:
            graph = GraphRepository(session)
            entities = await graph.all_entities(project_id)
            groups = find_duplicates(
                [
                    Candidate(e.id, e.name, e.type, e.mention_count, tuple(e.aliases))
                    for e in entities
                ]
            )
            merged = 0
            by_id = {e.id: e for e in entities}
            for group in groups:
                survivor = by_id[group.survivor]
                victims = [v for v in group.members if v in by_id]
                await graph.merge(project_id, survivor.id, victims)
                merged += len(victims)
                for reason in group.members.values():
                    metrics.ENTITIES_MERGED.labels(reason).inc()
            if merged:
                await graph.recount(project_id)
            await graph.refresh_degrees(project_id)
            await session.commit()
        return merged

    async def _write_reports(
        self,
        levels: list[list[CommunityNode]],
        entities: dict[uuid.UUID, Entity],
        relations: list[Relation],
        chunk_ids_by_relation: dict[uuid.UUID, list[str]],
    ) -> dict[tuple[int, int], tuple[Report, str]]:
        """Reports bottom-up: a parent is summarized from its children's reports."""
        names = {str(i): e.name for i, e in entities.items()}
        reports: dict[tuple[int, int], tuple[Report, str]] = {}
        gate = asyncio.Semaphore(REPORT_CONCURRENCY)
        reporter = self.c.reporter

        async def one(node: CommunityNode) -> None:
            members = node.members
            briefs = [
                EntityBrief(str(i), e.name, e.type, e.description, e.importance, e.degree)
                for i, e in entities.items()
                if str(i) in members
            ]
            inside = [
                RelationBrief(
                    names[str(r.source_id)],
                    names[str(r.target_id)],
                    r.predicate,
                    r.description,
                    r.weight,
                    tuple(chunk_ids_by_relation.get(r.id, ())),
                )
                for r in relations
                if str(r.source_id) in members and str(r.target_id) in members
            ]
            children = [
                ChildBrief(reports[c][0].title, reports[c][0].summary) for c in node.children
            ]
            async with gate:
                report = await reporter.report(ReportInput(node.level, briefs, inside, children))
            reports[node.ref] = (report, reporter.name)

        for level in reversed(levels):
            await asyncio.gather(*(one(node) for node in level))
        # Parents first, as the writer inserts them: levels ascending, ordinals ascending.
        return dict(sorted(reports.items()))

    # Recovery ---------------------------------------------------------------------------

    async def reap(self, cutoff: datetime) -> int:
        async with self.c.db.session() as session:
            jobs: list[Job] = []
            stuck = await BuildRepository(session).unfinished_before(cutoff)
            for build in stuck:
                if build.attempts >= MAX_ATTEMPTS:
                    build.status = BuildStatus.FAILED
                    build.error = "The build did not finish after several attempts."
                    build.finished_at = datetime.now(UTC)
                else:
                    build.status = BuildStatus.QUEUED
                    build.updated_at = datetime.now(UTC)
                    jobs.append(Job.build(build.project_id, build.id))
            await session.commit()
        for job in jobs:
            await self.c.queue.enqueue(job)
        return len(stuck)


def _node(levels: list[list[CommunityNode]], ref: tuple[int, int]) -> CommunityNode:
    return levels[ref[0]][ref[1]]


def _message(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.message
    return "The build failed. Try again."
