"""Entities, relations, duplicate resolution and the explorer view."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from graphrag.api.deps import ContainerDep, EditorDep, SessionDep, ViewerDep
from graphrag.repositories.graph import EntityFilter
from graphrag.schemas.common import Page
from graphrag.schemas.graph import (
    DuplicateGroup,
    EntityDetail,
    EntityListItem,
    EntityOut,
    EntityUpdate,
    ExploreOut,
    MergeRequest,
    MergeResult,
)
from graphrag.services.graph import GraphService

router = APIRouter(prefix="/api/v1/projects/{project}/graph", tags=["graph"])
TypesQuery = Annotated[
    list[str] | None,
    Query(alias="type", description="Entity types to keep; repeat the parameter for several."),
]


def _filter(
    q: str | None,
    types: list[str] | None,
    community: uuid.UUID | None,
    document: uuid.UUID | None,
    min_degree: int,
) -> EntityFilter:
    return EntityFilter(
        query=q,
        types=[t.upper() for t in types or []],
        community_id=community,
        document_id=document,
        min_degree=min_degree,
    )


@router.get("/entities", summary="Entities, filtered and paged")
async def list_entities(
    ctx: ViewerDep,
    container: ContainerDep,
    session: SessionDep,
    types: TypesQuery = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    community: uuid.UUID | None = None,
    document: uuid.UUID | None = None,
    min_degree: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[str, Query(pattern="^(importance|name|mentions|type)$")] = "importance",
    level: Annotated[int, Query(ge=0, le=4, description="Community level shown per entity.")] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EntityListItem]:
    items, total = await GraphService(container, session).entities(
        ctx.project,
        _filter(q, types, community, document, min_degree),
        sort=sort,
        level=level,
        limit=limit,
        offset=offset,
    )
    return Page[EntityListItem](items=items, total=total, limit=limit, offset=offset)


@router.get("/entities/{entity_id}", summary="An entity with its relations and source passages")
async def get_entity(
    entity_id: uuid.UUID, ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> EntityDetail:
    return await GraphService(container, session).detail(ctx.project, entity_id)


@router.patch("/entities/{entity_id}", summary="Rename, retype or describe an entity")
async def update_entity(
    entity_id: uuid.UUID,
    body: EntityUpdate,
    ctx: EditorDep,
    container: ContainerDep,
    session: SessionDep,
) -> EntityOut:
    return await GraphService(container, session).update(
        ctx.project,
        ctx.principal,
        entity_id,
        name=body.name,
        type_=body.type,
        description=body.description,
    )


@router.delete("/entities/{entity_id}", summary="Delete an entity", status_code=204)
async def delete_entity(
    entity_id: uuid.UUID, ctx: EditorDep, container: ContainerDep, session: SessionDep
) -> None:
    await GraphService(container, session).delete(ctx.project, ctx.principal, entity_id)


@router.get("/explore", summary="A subgraph for the explorer: nodes, edges and legends")
async def explore(
    ctx: ViewerDep,
    container: ContainerDep,
    session: SessionDep,
    types: TypesQuery = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    community: uuid.UUID | None = None,
    document: uuid.UUID | None = None,
    min_degree: Annotated[int, Query(ge=0)] = 0,
    min_weight: Annotated[float, Query(ge=0)] = 0.0,
    level: Annotated[int, Query(ge=0, le=4, description="Community level used for colors.")] = 0,
    limit: Annotated[int, Query(ge=1, le=400)] = 150,
    focus: Annotated[
        uuid.UUID | None, Query(description="Show this entity's neighborhood.")
    ] = None,
    hops: Annotated[int, Query(ge=1, le=3)] = 1,
) -> ExploreOut:
    return await GraphService(container, session).explore(
        ctx.project,
        _filter(q, types, community, document, min_degree),
        level=level,
        limit=limit,
        focus=focus,
        hops=hops,
        min_weight=min_weight,
    )


@router.get("/duplicates", summary="Entities that look like the same thing")
async def duplicates(
    ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> list[DuplicateGroup]:
    return await GraphService(container, session).duplicates(ctx.project)


@router.post("/merge", summary="Merge entities into one")
async def merge_entities(
    body: MergeRequest, ctx: EditorDep, container: ContainerDep, session: SessionDep
) -> MergeResult:
    survivor, merged = await GraphService(container, session).merge(
        ctx.project, ctx.principal, body.survivor_id, body.entity_ids
    )
    return MergeResult(survivor=EntityOut.model_validate(survivor), merged=merged)
