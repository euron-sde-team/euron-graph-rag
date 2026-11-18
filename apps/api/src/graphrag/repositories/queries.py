from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from graphrag.models import QueryLog
from graphrag.repositories.base import Repository


class QueryLogRepository(Repository):
    async def add(self, row: QueryLog) -> QueryLog:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, project_id: uuid.UUID, query_id: uuid.UUID) -> QueryLog | None:
        result = await self.session.execute(
            select(QueryLog).where(QueryLog.id == query_id, QueryLog.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def page(
        self, project_id: uuid.UUID, *, mode: str | None, limit: int, offset: int
    ) -> tuple[list[QueryLog], int]:
        conditions: list[Any] = [QueryLog.project_id == project_id]
        if mode:
            conditions.append(QueryLog.mode == mode)
        total = int(await self.session.scalar(select(func.count()).where(*conditions)) or 0)
        result = await self.session.execute(
            select(QueryLog)
            .where(*conditions)
            .order_by(QueryLog.created_at.desc(), QueryLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total

    async def daily(self, project_id: uuid.UUID, since: datetime) -> list[tuple[Any, int, float]]:
        day = func.date_trunc("day", QueryLog.created_at)
        result = await self.session.execute(
            select(day, func.count(), func.coalesce(func.avg(QueryLog.latency_ms), 0))
            .where(QueryLog.project_id == project_id, QueryLog.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(d, int(n), float(ms)) for d, n, ms in result.all()]

    async def by_mode(self, project_id: uuid.UUID) -> list[tuple[str, int, float]]:
        result = await self.session.execute(
            select(QueryLog.mode, func.count(), func.coalesce(func.avg(QueryLog.latency_ms), 0))
            .where(QueryLog.project_id == project_id)
            .group_by(QueryLog.mode)
            .order_by(QueryLog.mode)
        )
        return [(m, int(n), float(ms)) for m, n, ms in result.all()]
