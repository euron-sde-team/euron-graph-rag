from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, Field

from graphrag.schemas.common import ApiModel, StrictModel


class TextSource(StrictModel):
    type: Literal["text"] = "text"
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=2_000_000)
    format: Literal["text", "markdown"] = "text"
    external_id: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UrlSource(StrictModel):
    type: Literal["url"] = "url"
    url: AnyHttpUrl
    title: str | None = Field(default=None, max_length=300)
    external_id: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


Source = Annotated[TextSource | UrlSource, Field(discriminator="type")]


class DocumentImport(StrictModel):
    items: list[Source] = Field(min_length=1, max_length=100)


class DocumentUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    metadata: dict[str, Any] | None = None


class DocumentOut(ApiModel):
    id: uuid.UUID
    external_id: str
    title: str
    source_type: str
    source_uri: str | None
    kind: str | None
    size_bytes: int
    metadata: dict[str, Any] = Field(validation_alias="meta")
    status: str
    stage: str
    error: str | None
    section_count: int
    token_count: int
    chunk_count: int
    entity_count: int
    relation_count: int
    created_at: datetime
    parsed_at: datetime | None
    extracted_at: datetime | None


class ChunkOut(ApiModel):
    id: uuid.UUID
    ordinal: int
    heading: str
    location: str
    text: str
    token_count: int


class DocumentEntityOut(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    mentions: int


class DocumentDetail(DocumentOut):
    entities: list[DocumentEntityOut]


class RejectedSource(ApiModel):
    name: str
    code: str
    message: str


class IngestResult(ApiModel):
    created: list[DocumentOut]
    duplicates: list[DocumentOut]
    rejected: list[RejectedSource]
