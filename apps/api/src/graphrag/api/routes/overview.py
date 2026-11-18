from __future__ import annotations

from fastapi import APIRouter

from graphrag.api.deps import ContainerDep, SessionDep, ViewerDep
from graphrag.schemas.overview import OverviewOut
from graphrag.services.overview import OverviewService

router = APIRouter(prefix="/api/v1/projects/{project}", tags=["overview"])


@router.get("/overview", summary="Graph size, pipeline state, communities and query traffic")
async def overview(ctx: ViewerDep, container: ContainerDep, session: SessionDep) -> OverviewOut:
    return await OverviewService(container, session).overview(ctx.project)
