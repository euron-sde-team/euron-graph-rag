"""Communities, their reports and the builds that produce them."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from graphrag.api.deps import ContainerDep, EditorDep, SessionDep, ViewerDep, rate_limit
from graphrag.schemas.common import Page
from graphrag.schemas.communities import BuildOut, CommunityDetail, CommunityOut, TreeNode
from graphrag.services.builds import BuildService
from graphrag.services.communities import CommunityService

router = APIRouter(prefix="/api/v1/projects/{project}", tags=["communities"])
builds = APIRouter(prefix="/api/v1/projects/{project}/builds", tags=["builds"])


@router.get("/communities", summary="Communities with their reports")
async def list_communities(
    ctx: ViewerDep,
    container: ContainerDep,
    session: SessionDep,
    level: Annotated[int | None, Query(ge=0, le=4)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    parent: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CommunityOut]:
    items, total = await CommunityService(container, session).page(
        ctx.project, level=level, query=q, parent_id=parent, limit=limit, offset=offset
    )
    return Page[CommunityOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/communities/tree", summary="Every community with its parent, for the hierarchy view")
async def community_tree(
    ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> list[TreeNode]:
    return await CommunityService(container, session).tree(ctx.project)


@router.get("/communities/{community_id}", summary="A community: report, findings and members")
async def get_community(
    community_id: uuid.UUID, ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> CommunityDetail:
    return await CommunityService(container, session).detail(ctx.project, community_id)


@builds.get("", summary="Graph builds, newest first")
async def list_builds(
    ctx: ViewerDep,
    container: ContainerDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[BuildOut]:
    items, total = await CommunityService(container, session).build_page(
        ctx.project, limit=limit, offset=offset
    )
    return Page[BuildOut](items=items, total=total, limit=limit, offset=offset)


@builds.post(
    "",
    summary="Rebuild communities and reports",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("build", "rate_limit_build"))],
)
async def request_build(ctx: EditorDep, container: ContainerDep, session: SessionDep) -> BuildOut:
    build = await BuildService(container, session).request(ctx.project, ctx.principal)
    return BuildOut.model_validate(build)


@builds.get("/{build_id}", summary="One build")
async def get_build(
    build_id: uuid.UUID, ctx: ViewerDep, container: ContainerDep, session: SessionDep
) -> BuildOut:
    return await CommunityService(container, session).build(ctx.project, build_id)
