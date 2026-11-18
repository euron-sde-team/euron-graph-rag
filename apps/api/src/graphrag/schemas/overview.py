from __future__ import annotations

import uuid
from datetime import datetime

from graphrag.schemas.common import ApiModel
from graphrag.schemas.communities import BuildOut
from graphrag.schemas.graph import TypeCount


class Counts(ApiModel):
    documents: int
    chunks: int
    entities: int
    relations: int
    communities: int
    queries: int


class PredicateCount(ApiModel):
    predicate: str
    count: int


class LevelCount(ApiModel):
    level: int
    count: int


class TopEntity(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    degree: int
    mention_count: int


class DayTraffic(ApiModel):
    day: datetime
    queries: int
    avg_latency_ms: float


class ModeTraffic(ApiModel):
    mode: str
    queries: int
    avg_latency_ms: float


class PipelineState(ApiModel):
    queued: int
    processing: int
    ready: int
    failed: int


class OverviewOut(ApiModel):
    counts: Counts
    pipeline: PipelineState
    entity_types: list[TypeCount]
    predicates: list[PredicateCount]
    community_levels: list[LevelCount]
    top_entities: list[TopEntity]
    traffic: list[DayTraffic]
    modes: list[ModeTraffic]
    latest_build: BuildOut | None
    pending_build: BuildOut | None
    graph_version: int
