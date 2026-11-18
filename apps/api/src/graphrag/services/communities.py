"""Communities and builds as the API presents them."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from graphrag.core.errors import NotFoundError
from graphrag.models import Community, Project
from graphrag.repositories.chunks import ChunkRepository
from graphrag.repositories.communities import BuildRepository, CommunityRepository
from graphrag.schemas.communities import (
    BuildOut,
    CommunityDetail,
    CommunityOut,
    FindingOut,
    SourceRef,
    TreeNode,
)
from graphrag.schemas.graph import EntityBrief
from graphrag.services.container import Container

MEMBER_LIMIT = 200


class CommunityService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.communities = CommunityRepository(session)
        self.builds = BuildRepository(session)

    async def page(
        self,
        project: Project,
        *,
        level: int | None,
        query: str | None,
        parent_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[CommunityOut], int]:
        rows, total = await self.communities.page(
            project.id, level=level, query=query, parent_id=parent_id, limit=limit, offset=offset
        )
        return [CommunityOut.model_validate(c) for c in rows], total

    async def tree(self, project: Project) -> list[TreeNode]:
        return [
            TreeNode(
                id=c.id,
                parent_id=c.parent_id,
                level=c.level,
                title=c.title,
                entity_count=c.entity_count,
                rank=c.rank,
            )
            for c in await self.communities.tree(project.id)
        ]

    async def detail(self, project: Project, community_id: uuid.UUID) -> CommunityDetail:
        community = await self.communities.get(project.id, community_id)
        if community is None:
            raise NotFoundError("Community not found.")
        members = await self.communities.members(community.id, MEMBER_LIMIT)
        children = await self.communities.children(community.id)
        parent: Community | None = (
            await self.communities.get(project.id, community.parent_id)
            if community.parent_id
            else None
        )
        wanted = {uuid.UUID(c) for f in community.findings for c in f.get("chunk_ids", [])}
        chunks = await ChunkRepository(self.session).hydrate(project.id, list(wanted))
        findings = [
            FindingOut(
                summary=f["summary"],
                explanation=f.get("explanation", ""),
                sources=[
                    SourceRef(
                        chunk_id=chunks[uuid.UUID(c)].id,
                        document_id=chunks[uuid.UUID(c)].document_id,
                        document_title=chunks[uuid.UUID(c)].document_title,
                        location=chunks[uuid.UUID(c)].location,
                    )
                    for c in f.get("chunk_ids", [])
                    if uuid.UUID(c) in chunks
                ],
            )
            for f in community.findings
        ]
        return CommunityDetail.model_validate(
            {
                **CommunityOut.model_validate(community).model_dump(),
                "findings": findings,
                "members": [EntityBrief.model_validate(m) for m in members],
                "children": [CommunityOut.model_validate(c) for c in children],
                "parent": CommunityOut.model_validate(parent) if parent else None,
            }
        )

    async def build_page(
        self, project: Project, *, limit: int, offset: int
    ) -> tuple[list[BuildOut], int]:
        rows, total = await self.builds.page(project.id, limit=limit, offset=offset)
        return [BuildOut.model_validate(b) for b in rows], total

    async def build(self, project: Project, build_id: uuid.UUID) -> BuildOut:
        row = await self.builds.get(project.id, build_id)
        if row is None:
            raise NotFoundError("Build not found.")
        return BuildOut.model_validate(row)
