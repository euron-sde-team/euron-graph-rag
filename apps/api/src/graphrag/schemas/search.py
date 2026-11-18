from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from graphrag.schemas.common import ApiModel, StrictModel


class QueryRequest(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    mode: Literal["local", "global", "hybrid"] = "hybrid"
    top_k: int = Field(default=6, ge=1, le=20, description="Chunks kept as sources.")
    hops: int = Field(default=1, ge=0, le=3, description="Graph distance explored from seeds.")
    level: int | None = Field(
        default=None, ge=0, le=4, description="Community level for global search."
    )
    cache: bool = Field(default=True, description="Serve an identical recent answer from cache.")


class CitationOut(ApiModel):
    n: int
    kind: Literal["chunk", "community"]
    id: uuid.UUID
    label: str
    snippet: str
    score: float
    cited: bool
    document_id: uuid.UUID | None = None
    document_title: str | None = None
    location: str | None = None
    supports: list[uuid.UUID] = Field(default_factory=list)


class NodeUse(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    role: Literal["seed", "neighbor"]
    score: float
    degree: int


class EdgeUse(ApiModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    predicate: str
    weight: float


class CommunityUse(ApiModel):
    id: uuid.UUID
    level: int
    title: str
    score: float
    points: list[str] = Field(default_factory=list)


class StepOut(ApiModel):
    name: str
    detail: str
    ms: float


class QueryResponse(ApiModel):
    id: uuid.UUID
    mode: str
    question: str
    answer: str
    answerer: str
    citations: list[CitationOut]
    nodes: list[NodeUse]
    edges: list[EdgeUse]
    communities: list[CommunityUse]
    steps: list[StepOut]
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    cached: bool
    created_at: datetime


class QuerySummary(ApiModel):
    id: uuid.UUID
    mode: str
    question: str
    answer: str
    answerer: str
    citation_count: int
    latency_ms: int
    cached: bool
    created_at: datetime
