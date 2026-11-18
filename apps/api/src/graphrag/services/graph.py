"""The knowledge graph as the web app and API clients read and edit it."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from graphrag.core.errors import NotFoundError, UnprocessableError
from graphrag.graph.names import display_name, entity_key
from graphrag.graph.resolution import Candidate, find_duplicates, merged_type
from graphrag.models import Community, Entity, Project, RelationEvidence
from graphrag.repositories.communities import CommunityRepository
from graphrag.repositories.graph import EntityFilter, GraphRepository
from graphrag.schemas.graph import (
    CommunityRef,
    DuplicateGroup,
    DuplicateMember,
    EntityBrief,
    EntityDetail,
    EntityListItem,
    EntityOut,
    ExploreCommunity,
    ExploreEdge,
    ExploreNode,
    ExploreOut,
    NeighborOut,
    RelationOut,
    SourceOut,
    TypeCount,
)
from graphrag.services import audit
from graphrag.services.builds import BuildService
from graphrag.services.container import Container
from graphrag.services.principal import Principal

MAX_EXPLORE_NODES = 400
NEIGHBOR_LIMIT = 80
SOURCE_LIMIT = 12


def community_ref(community: Community) -> CommunityRef:
    return CommunityRef(
        id=community.id, level=community.level, ordinal=community.ordinal, title=community.title
    )


class GraphService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.graph = GraphRepository(session)
        self.communities = CommunityRepository(session)

    async def entities(
        self,
        project: Project,
        flt: EntityFilter,
        *,
        sort: str,
        level: int,
        limit: int,
        offset: int,
    ) -> tuple[list[EntityListItem], int]:
        rows, total = await self.graph.page(project.id, flt, sort=sort, limit=limit, offset=offset)
        placed = await self.graph.community_levels_of(project.id, [e.id for e in rows], level)
        items = [
            EntityListItem.model_validate(
                {
                    **EntityOut.model_validate(e).model_dump(),
                    "community": community_ref(placed[e.id]) if e.id in placed else None,
                }
            )
            for e in rows
        ]
        return items, total

    async def detail(self, project: Project, entity_id: uuid.UUID) -> EntityDetail:
        entity = await self.graph.get_entity(project.id, entity_id)
        if entity is None:
            raise NotFoundError("Entity not found.")
        relations = await self.graph.relations_of(project.id, [entity_id], limit=NEIGHBOR_LIMIT)
        other_ids = {r.target_id if r.source_id == entity_id else r.source_id for r in relations}
        others = await self.graph.get_entities(project.id, other_ids)
        evidence = await self.graph.evidence_for(project.id, [r.id for r in relations])
        first_evidence: dict[uuid.UUID, RelationEvidence] = {}
        for item in evidence:
            first_evidence.setdefault(item.relation_id, item)
        neighbors = []
        for r in relations:
            outgoing = r.source_id == entity_id
            other = others.get(r.target_id if outgoing else r.source_id)
            if other is None:
                continue
            support = first_evidence.get(r.id)
            neighbors.append(
                NeighborOut(
                    relation=RelationOut.model_validate(r),
                    direction="out" if outgoing else "in",
                    entity=EntityBrief.model_validate(other),
                    quote=support.quote if support else "",
                    chunk_id=support.chunk_id if support else None,
                )
            )
        memberships = await self.communities.for_entities(project.id, [entity_id])
        mentions = await self.graph.mention_chunks(project.id, entity_id, SOURCE_LIMIT)
        sources = [
            SourceOut(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=title,
                location=chunk.location,
                heading=chunk.heading,
                text=chunk.text,
                surface=surface,
                count=count,
            )
            for chunk, title, surface, count in mentions
        ]
        return EntityDetail.model_validate(
            {
                **EntityOut.model_validate(entity).model_dump(),
                "created_at": entity.created_at,
                "communities": [community_ref(c) for _, c in memberships],
                "neighbors": neighbors,
                "sources": sources,
            }
        )

    async def explore(
        self,
        project: Project,
        flt: EntityFilter,
        *,
        level: int,
        limit: int,
        focus: uuid.UUID | None,
        hops: int,
        min_weight: float,
    ) -> ExploreOut:
        limit = min(limit, MAX_EXPLORE_NODES)
        total_entities, total_relations = await self.graph.counts(project.id)
        matching = (await self.graph.page(project.id, flt, sort="importance", limit=1, offset=0))[1]
        if focus is not None:
            entities = await self._neighborhood(project.id, focus, hops, limit, flt)
        else:
            entities = await self.graph.top(project.id, flt, limit)
        ids = [e.id for e in entities]
        relations = await self.graph.relations_among(project.id, ids, min_weight=min_weight)
        placed = await self.graph.community_levels_of(project.id, ids, level)
        nodes = [
            ExploreNode(
                id=e.id,
                name=e.name,
                type=e.type,
                degree=e.degree,
                importance=e.importance,
                mention_count=e.mention_count,
                community_id=placed[e.id].id if e.id in placed else None,
                community_ordinal=placed[e.id].ordinal if e.id in placed else None,
            )
            for e in entities
        ]
        legend: dict[uuid.UUID, ExploreCommunity] = {}
        for e in entities:
            community = placed.get(e.id)
            if community is None:
                continue
            entry = legend.setdefault(
                community.id,
                ExploreCommunity(
                    id=community.id, ordinal=community.ordinal, title=community.title, count=0
                ),
            )
            entry.count += 1
        kinds = Counter(e.type for e in entities)
        return ExploreOut(
            nodes=nodes,
            edges=[
                ExploreEdge(
                    id=r.id,
                    source=r.source_id,
                    target=r.target_id,
                    predicate=r.predicate,
                    weight=r.weight,
                )
                for r in relations
            ],
            total_entities=total_entities,
            total_relations=total_relations,
            truncated=matching > len(entities),
            types=[TypeCount(type=t, count=n) for t, n in kinds.most_common()],
            communities=sorted(legend.values(), key=lambda c: c.ordinal),
            focus=focus,
        )

    async def _neighborhood(
        self, project_id: uuid.UUID, focus: uuid.UUID, hops: int, limit: int, flt: EntityFilter
    ) -> list[Entity]:
        if await self.graph.get_entity(project_id, focus) is None:
            raise NotFoundError("Entity not found.")
        seen: dict[uuid.UUID, int] = {focus: 0}
        frontier = {focus}
        for depth in range(1, max(1, hops) + 1):
            relations = await self.graph.relations_of(project_id, frontier, limit=limit * 2)
            reached: set[uuid.UUID] = set()
            for r in relations:
                for end in (r.source_id, r.target_id):
                    if end not in seen:
                        seen[end] = depth
                        reached.add(end)
            frontier = reached
            if not frontier or len(seen) >= limit:
                break
        found = await self.graph.get_entities(project_id, list(seen))
        allowed = set(flt.types)
        ordered = sorted(
            found.values(),
            key=lambda e: (e.id != focus, seen[e.id], -e.importance, e.name),
        )
        return [e for e in ordered if e.id == focus or not allowed or e.type in allowed][:limit]

    async def update(
        self,
        project: Project,
        principal: Principal,
        entity_id: uuid.UUID,
        *,
        name: str | None,
        type_: str | None,
        description: str | None,
    ) -> EntityOut:
        entity = await self.graph.get_entity(project.id, entity_id)
        if entity is None:
            raise NotFoundError("Entity not found.")
        if name is not None:
            shown = display_name(name)
            key = entity_key(shown)
            if not key:
                raise UnprocessableError("That name has no letters or digits.")
            if key != entity.key and key in await self.graph.alias_index(project.id):
                raise UnprocessableError(
                    "Another entity already has that name; merge the two instead.",
                    code="name_taken",
                )
            if shown != entity.name:
                entity.aliases = [a for a in entity.aliases if entity_key(a) != key]
                if entity.name not in entity.aliases:
                    entity.aliases = [*entity.aliases, entity.name]
            entity.name, entity.key = shown, key
        if type_ is not None:
            entity.type = type_.strip().upper().replace(" ", "_")
        if description is not None:
            entity.description = description.strip()
        await audit.record(
            self.session,
            project_id=project.id,
            principal=principal,
            action="entity.updated",
            target_type="entity",
            target_id=entity.id,
            details={"name": entity.name},
        )
        project.graph_version += 1
        await self.session.commit()
        return EntityOut.model_validate(entity)

    async def delete(self, project: Project, principal: Principal, entity_id: uuid.UUID) -> None:
        entity = await self.graph.get_entity(project.id, entity_id)
        if entity is None:
            raise NotFoundError("Entity not found.")
        await self.session.delete(entity)
        await self.session.flush()
        await self.graph.recount(project.id)
        await self.graph.refresh_degrees(project.id)
        await audit.record(
            self.session,
            project_id=project.id,
            principal=principal,
            action="entity.deleted",
            target_type="entity",
            target_id=entity_id,
            details={"name": entity.name},
        )
        builds = BuildService(self.c, self.session)
        await builds.graph_changed(project, principal.user_id)
        await self.session.commit()
        await builds.dispatch_pending(project)

    async def duplicates(self, project: Project) -> list[DuplicateGroup]:
        """What a build would merge, so a person can see it before and after."""
        entities = {e.id: e for e in await self.graph.all_entities(project.id)}
        groups = find_duplicates(
            [
                Candidate(e.id, e.name, e.type, e.mention_count, tuple(e.aliases))
                for e in entities.values()
            ]
        )

        def member(entity: Entity, reason: str) -> DuplicateMember:
            return DuplicateMember(
                id=entity.id,
                name=entity.name,
                type=entity.type,
                mention_count=entity.mention_count,
                reason=reason,
            )

        return [
            DuplicateGroup(
                survivor=member(entities[g.survivor], "survivor"),
                members=[member(entities[m], reason) for m, reason in g.members.items()],
            )
            for g in groups
        ]

    async def merge(
        self,
        project: Project,
        principal: Principal,
        survivor_id: uuid.UUID,
        entity_ids: Sequence[uuid.UUID],
    ) -> tuple[Entity, int]:
        victims = [i for i in dict.fromkeys(entity_ids) if i != survivor_id]
        if not victims:
            raise UnprocessableError("Pick at least one other entity to merge in.")
        found = await self.graph.get_entities(project.id, [survivor_id, *victims])
        if len(found) != len(victims) + 1:
            raise NotFoundError("One of the entities was not found.")
        survivor = found[survivor_id]
        survivor.type = merged_type(survivor.type, [found[v].type for v in victims])
        await self.graph.merge(project.id, survivor_id, victims)
        await self.session.flush()
        await self.graph.recount(project.id)
        await self.graph.refresh_degrees(project.id)
        await audit.record(
            self.session,
            project_id=project.id,
            principal=principal,
            action="entity.merged",
            target_type="entity",
            target_id=survivor_id,
            details={"merged": len(victims), "names": [found[v].name for v in victims][:10]},
        )
        builds = BuildService(self.c, self.session)
        await builds.graph_changed(project, principal.user_id)
        await self.session.commit()
        await builds.dispatch_pending(project)
        return survivor, len(victims)
