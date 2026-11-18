"""The dashboard: graph size, pipeline state, communities and traffic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from graphrag.models import Project
from graphrag.models.enums import JobStatus
from graphrag.repositories.chunks import ChunkRepository
from graphrag.repositories.communities import BuildRepository, CommunityRepository
from graphrag.repositories.documents import DocumentRepository
from graphrag.repositories.graph import EntityFilter, GraphRepository
from graphrag.repositories.queries import QueryLogRepository
from graphrag.schemas.communities import BuildOut
from graphrag.schemas.graph import TypeCount
from graphrag.schemas.overview import (
    Counts,
    DayTraffic,
    LevelCount,
    ModeTraffic,
    OverviewOut,
    PipelineState,
    PredicateCount,
    TopEntity,
)
from graphrag.services.container import Container

TRAFFIC_DAYS = 14


class OverviewService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session

    async def overview(self, project: Project) -> OverviewOut:
        graph = GraphRepository(self.session)
        communities = CommunityRepository(self.session)
        builds = BuildRepository(self.session)
        logs = QueryLogRepository(self.session)
        documents = DocumentRepository(self.session)

        status = await documents.status_counts(project.id)
        entities, relations = await graph.counts(project.id)
        levels = await communities.level_counts(project.id)
        modes = await logs.by_mode(project.id)
        since = datetime.now(UTC) - timedelta(days=TRAFFIC_DAYS)
        latest = await builds.latest_completed(project.id)
        pending = await builds.running(project.id) or await builds.pending(project.id)
        top = await graph.top(project.id, EntityFilter(), 8)
        return OverviewOut(
            counts=Counts(
                documents=sum(status.values()),
                chunks=await ChunkRepository(self.session).count(project.id),
                entities=entities,
                relations=relations,
                communities=sum(n for _, n in levels),
                queries=sum(n for _, n, _ in modes),
            ),
            pipeline=PipelineState(
                queued=status.get(JobStatus.QUEUED, 0),
                processing=status.get(JobStatus.PROCESSING, 0),
                ready=status.get(JobStatus.READY, 0),
                failed=status.get(JobStatus.FAILED, 0),
            ),
            entity_types=[
                TypeCount(type=t, count=n) for t, n in await graph.type_counts(project.id)
            ],
            predicates=[
                PredicateCount(predicate=p, count=n)
                for p, n in await graph.predicate_counts(project.id)
            ],
            community_levels=[LevelCount(level=level, count=n) for level, n in levels],
            top_entities=[
                TopEntity(
                    id=e.id,
                    name=e.name,
                    type=e.type,
                    degree=e.degree,
                    mention_count=e.mention_count,
                )
                for e in top
            ],
            traffic=[
                DayTraffic(day=day, queries=n, avg_latency_ms=round(ms, 1))
                for day, n, ms in await logs.daily(project.id, since)
            ],
            modes=[
                ModeTraffic(mode=m, queries=n, avg_latency_ms=round(ms, 1)) for m, n, ms in modes
            ],
            latest_build=BuildOut.model_validate(latest) if latest else None,
            pending_build=BuildOut.model_validate(pending) if pending else None,
            graph_version=project.graph_version,
        )
