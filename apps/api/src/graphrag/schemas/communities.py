from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from graphrag.schemas.common import ApiModel
from graphrag.schemas.graph import EntityBrief


class SourceRef(ApiModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    location: str


class FindingOut(ApiModel):
    summary: str
    explanation: str
    sources: list[SourceRef]


class CommunityOut(ApiModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    level: int
    ordinal: int
    title: str
    summary: str
    entity_count: int
    relation_count: int
    rank: float
    reporter: str


class CommunityDetail(CommunityOut):
    findings: list[FindingOut]
    members: list[EntityBrief]
    children: list[CommunityOut]
    parent: CommunityOut | None


class TreeNode(ApiModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    level: int
    title: str
    entity_count: int
    rank: float


class BuildOut(ApiModel):
    id: uuid.UUID
    status: str
    trigger: str
    params: dict[str, Any]
    stats: dict[str, Any]
    error: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
