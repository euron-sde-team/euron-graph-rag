"""Communities and the builds that produce them."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import Float, bindparam, cast, delete, func, insert, literal_column, or_, select

from graphrag.db.types import SUPPORTED_DIMS, Embedding
from graphrag.models import Community, CommunityMember, Entity, GraphBuild
from graphrag.models.enums import BuildStatus
from graphrag.repositories.base import Repository


@dataclass(frozen=True, slots=True)
class CommunityRow:
    id: uuid.UUID
    parent_id: uuid.UUID | None
    level: int
    ordinal: int
    title: str
    summary: str
    findings: list[dict[str, Any]]
    entity_count: int
    relation_count: int
    rank: float
    reporter: str
    embedding: np.ndarray
    members: Sequence[uuid.UUID]


class CommunityRepository(Repository):
    async def replace_all(
        self, project_id: uuid.UUID, build_id: uuid.UUID, rows: Sequence[CommunityRow], dim: int
    ) -> None:
        """Swap the project's communities for a new build's in one transaction, so readers
        see the old set or the new one and never a mixture."""
        await self.session.execute(delete(Community).where(Community.project_id == project_id))
        # Parents are inserted before their children: the foreign key checks each row.
        ordered = sorted(rows, key=lambda r: r.level)
        if ordered:
            await self.session.execute(
                insert(Community),
                [
                    {
                        "id": r.id,
                        "project_id": project_id,
                        "build_id": build_id,
                        "parent_id": r.parent_id,
                        "level": r.level,
                        "ordinal": r.ordinal,
                        "title": r.title[:300],
                        "summary": r.summary,
                        "findings": r.findings,
                        "entity_count": r.entity_count,
                        "relation_count": r.relation_count,
                        "rank": r.rank,
                        "reporter": r.reporter[:32],
                        "embedding": r.embedding,
                        "embedding_dim": dim,
                    }
                    for r in ordered
                ],
            )
            members = [
                {"community_id": r.id, "entity_id": entity_id, "project_id": project_id}
                for r in ordered
                for entity_id in r.members
            ]
            for start in range(0, len(members), 5000):
                await self.session.execute(insert(CommunityMember), members[start : start + 5000])

    async def get(self, project_id: uuid.UUID, community_id: uuid.UUID) -> Community | None:
        result = await self.session.execute(
            select(Community).where(
                Community.id == community_id, Community.project_id == project_id
            )
        )
        return result.scalar_one_or_none()

    async def get_many(
        self, project_id: uuid.UUID, ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, Community]:
        if not ids:
            return {}
        result = await self.session.execute(
            select(Community).where(Community.project_id == project_id, Community.id.in_(list(ids)))
        )
        return {c.id: c for c in result.scalars()}

    async def page(
        self,
        project_id: uuid.UUID,
        *,
        level: int | None,
        query: str | None,
        parent_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Community], int]:
        conditions: list[Any] = [Community.project_id == project_id]
        if level is not None:
            conditions.append(Community.level == level)
        if parent_id is not None:
            conditions.append(Community.parent_id == parent_id)
        if query:
            pattern = f"%{query.strip()}%"
            conditions.append(or_(Community.title.ilike(pattern), Community.summary.ilike(pattern)))
        total = int(await self.session.scalar(select(func.count()).where(*conditions)) or 0)
        result = await self.session.execute(
            select(Community)
            .where(*conditions)
            .order_by(Community.level, Community.rank.desc(), Community.ordinal)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total

    async def tree(self, project_id: uuid.UUID) -> list[Community]:
        result = await self.session.execute(
            select(Community)
            .where(Community.project_id == project_id)
            .order_by(Community.level, Community.rank.desc(), Community.ordinal)
        )
        return list(result.scalars())

    async def level_counts(self, project_id: uuid.UUID) -> list[tuple[int, int]]:
        result = await self.session.execute(
            select(Community.level, func.count())
            .where(Community.project_id == project_id)
            .group_by(Community.level)
            .order_by(Community.level)
        )
        return [(int(level), int(n)) for level, n in result.all()]

    async def at_level(self, project_id: uuid.UUID, level: int) -> list[Community]:
        """The communities describing the whole graph at `level`: that level's, plus the
        shallower ones whose branch stops splitting before it."""
        child = Community.__table__.alias("child")
        leaf = ~select(child.c.id).where(child.c.parent_id == Community.id).exists()
        result = await self.session.execute(
            select(Community)
            .where(
                Community.project_id == project_id,
                or_(Community.level == level, (Community.level < level) & leaf),
            )
            .order_by(Community.rank.desc(), Community.level, Community.ordinal)
        )
        return list(result.scalars())

    async def member_ids(self, community_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self.session.execute(
            select(CommunityMember.entity_id).where(CommunityMember.community_id == community_id)
        )
        return list(result.scalars())

    async def members(self, community_id: uuid.UUID, limit: int) -> list[Entity]:
        result = await self.session.execute(
            select(Entity)
            .join(CommunityMember, CommunityMember.entity_id == Entity.id)
            .where(CommunityMember.community_id == community_id)
            .order_by(Entity.importance.desc(), Entity.name)
            .limit(limit)
        )
        return list(result.scalars())

    async def children(self, community_id: uuid.UUID) -> list[Community]:
        result = await self.session.execute(
            select(Community)
            .where(Community.parent_id == community_id)
            .order_by(Community.rank.desc(), Community.ordinal)
        )
        return list(result.scalars())

    async def for_entities(
        self, project_id: uuid.UUID, entity_ids: Collection[uuid.UUID]
    ) -> list[tuple[uuid.UUID, Community]]:
        """Every community (any level) each entity belongs to."""
        if not entity_ids:
            return []
        result = await self.session.execute(
            select(CommunityMember.entity_id, Community)
            .join(Community, Community.id == CommunityMember.community_id)
            .where(
                CommunityMember.project_id == project_id,
                CommunityMember.entity_id.in_(list(entity_ids)),
            )
            .order_by(Community.level)
        )
        return [(entity_id, community) for entity_id, community in result.all()]

    async def vector_rank(
        self, project_id: uuid.UUID, dim: int, query: np.ndarray, ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, float]:
        """Cosine similarity of the question to each given community's report."""
        if dim not in SUPPORTED_DIMS:
            raise ValueError(f"unsupported embedding width {dim}")
        if not ids:
            return {}
        typed = cast(Community.embedding, Embedding(dim))
        distance = typed.op("<=>", return_type=Float)(
            bindparam("query_vector", value=query, type_=Embedding())
        )
        rows = (
            await self.session.execute(
                select(Community.id, (1 - distance).label("score")).where(
                    Community.project_id == project_id,
                    Community.id.in_(list(ids)),
                    Community.embedding_dim == literal_column(str(dim)),
                )
            )
        ).all()
        return {r.id: float(r.score) for r in rows}


class BuildRepository(Repository):
    async def add(self, build: GraphBuild) -> GraphBuild:
        self.session.add(build)
        await self.session.flush()
        return build

    async def get(self, project_id: uuid.UUID, build_id: uuid.UUID) -> GraphBuild | None:
        result = await self.session.execute(
            select(GraphBuild).where(GraphBuild.id == build_id, GraphBuild.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, build_id: uuid.UUID) -> GraphBuild | None:
        result = await self.session.execute(
            select(GraphBuild).where(GraphBuild.id == build_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def page(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[GraphBuild], int]:
        total = int(
            await self.session.scalar(
                select(func.count()).where(GraphBuild.project_id == project_id)
            )
            or 0
        )
        result = await self.session.execute(
            select(GraphBuild)
            .where(GraphBuild.project_id == project_id)
            .order_by(GraphBuild.created_at.desc(), GraphBuild.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total

    async def latest_completed(self, project_id: uuid.UUID) -> GraphBuild | None:
        result = await self.session.execute(
            select(GraphBuild)
            .where(GraphBuild.project_id == project_id, GraphBuild.status == BuildStatus.COMPLETED)
            .order_by(GraphBuild.finished_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def pending(self, project_id: uuid.UUID) -> GraphBuild | None:
        """A build that has not started yet: new work coalesces into it."""
        result = await self.session.execute(
            select(GraphBuild)
            .where(GraphBuild.project_id == project_id, GraphBuild.status == BuildStatus.QUEUED)
            .order_by(GraphBuild.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def running(self, project_id: uuid.UUID) -> GraphBuild | None:
        result = await self.session.execute(
            select(GraphBuild)
            .where(GraphBuild.project_id == project_id, GraphBuild.status == BuildStatus.RUNNING)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def unfinished_before(self, cutoff: datetime, limit: int = 50) -> list[GraphBuild]:
        result = await self.session.execute(
            select(GraphBuild)
            .where(
                GraphBuild.status.in_([BuildStatus.QUEUED, BuildStatus.RUNNING]),
                GraphBuild.updated_at < cutoff,
            )
            .order_by(GraphBuild.updated_at)
            .limit(limit)
        )
        return list(result.scalars())
