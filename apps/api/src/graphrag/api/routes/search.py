"""Questions with citations, and the history of what was asked."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from graphrag.api.deps import ContainerDep, SessionDep, ViewerDep, rate_limit
from graphrag.schemas.common import Page
from graphrag.schemas.search import QueryRequest, QueryResponse, QuerySummary
from graphrag.services.search import SearchService

router = APIRouter(prefix="/api/v1/projects/{project}", tags=["search"])


@router.post(
    "/query",
    summary="Ask a question: local, global or hybrid search with citations",
    dependencies=[Depends(rate_limit("query", "rate_limit_query"))],
)
async def ask(
    body: QueryRequest, ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> QueryResponse:
    return await SearchService(container, session).ask(ctx.project, ctx.principal, body)


@router.get("/queries", summary="Questions asked in this project, newest first")
async def list_queries(
    ctx: ViewerDep,
    container: ContainerDep,
    session: SessionDep,
    mode: Annotated[str | None, Query(pattern="^(local|global|hybrid)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[QuerySummary]:
    items, total = await SearchService(container, session).history(
        ctx.project, mode=mode, limit=limit, offset=offset
    )
    return Page[QuerySummary](items=items, total=total, limit=limit, offset=offset)


@router.get("/queries/{query_id}", summary="A past question with everything that answered it")
async def get_query(
    query_id: uuid.UUID, ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> QueryResponse:
    return await SearchService(container, session).get(ctx.project, query_id)
