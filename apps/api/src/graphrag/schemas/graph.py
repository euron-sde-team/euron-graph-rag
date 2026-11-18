from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from graphrag.schemas.common import ApiModel, StrictModel


class CommunityRef(ApiModel):
    id: uuid.UUID
    level: int
    ordinal: int
    title: str


class EntityOut(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    description: str
    aliases: list[str]
    mention_count: int
    degree: int
    importance: float


class EntityListItem(EntityOut):
    community: CommunityRef | None = None


class EntityBrief(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    degree: int


class RelationOut(ApiModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    predicate: str
    description: str
    weight: float
    evidence_count: int


class NeighborOut(ApiModel):
    relation: RelationOut
    direction: str = Field(description="out: this entity is the source; in: it is the target.")
    entity: EntityBrief
    quote: str = ""
    chunk_id: uuid.UUID | None = None


class SourceOut(ApiModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    location: str
    heading: str
    text: str
    surface: str
    count: int


class EntityDetail(EntityOut):
    created_at: datetime
    communities: list[CommunityRef]
    neighbors: list[NeighborOut]
    sources: list[SourceOut]


class ExploreNode(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    degree: int
    importance: float
    mention_count: int
    community_id: uuid.UUID | None = None
    community_ordinal: int | None = None


class ExploreEdge(ApiModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    predicate: str
    weight: float


class TypeCount(ApiModel):
    type: str
    count: int


class ExploreCommunity(ApiModel):
    id: uuid.UUID
    ordinal: int
    title: str
    count: int


class ExploreOut(ApiModel):
    nodes: list[ExploreNode]
    edges: list[ExploreEdge]
    total_entities: int
    total_relations: int
    truncated: bool
    types: list[TypeCount]
    communities: list[ExploreCommunity]
    focus: uuid.UUID | None = None


class MergeRequest(StrictModel):
    survivor_id: uuid.UUID
    entity_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class EntityUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, min_length=2, max_length=24)
    description: str | None = Field(default=None, max_length=2000)


class DuplicateMember(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    mention_count: int
    reason: str


class DuplicateGroup(ApiModel):
    survivor: DuplicateMember
    members: list[DuplicateMember]


class MergeResult(ApiModel):
    survivor: EntityOut
    merged: int


def entity_out(entity: Any) -> EntityOut:
    return EntityOut.model_validate(entity)
