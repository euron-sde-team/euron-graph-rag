from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import EmailStr, Field, field_validator

from graphrag.schemas.common import ApiModel, StrictModel

DEFAULT_ENTITY_TYPES = [
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "PRODUCT",
    "TECHNOLOGY",
    "EVENT",
    "CONCEPT",
    "OTHER",
]


class GraphSettings(StrictModel):
    """How a project turns documents into a graph. Changes apply to documents ingested after
    the change; reprocess a document to apply them to it."""

    entity_types: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ENTITY_TYPES),
        min_length=1,
        max_length=16,
        description="Entity types the extractor may emit. OTHER catches the rest.",
    )
    chunk_tokens: int = Field(default=220, ge=60, le=800)
    overlap_tokens: int = Field(default=30, ge=0, le=200)
    community_levels: int = Field(default=3, ge=1, le=4, description="Depth of the hierarchy.")
    resolution: float = Field(
        default=1.0,
        ge=0.2,
        le=3.0,
        description="Louvain resolution: higher gives smaller communities.",
    )
    auto_build: bool = Field(
        default=True, description="Rebuild communities after documents finish extracting."
    )

    @field_validator("entity_types")
    @classmethod
    def _clean_types(cls, value: list[str]) -> list[str]:
        cleaned = list(
            dict.fromkeys(t.strip().upper().replace(" ", "_") for t in value if t.strip())
        )
        if not cleaned:
            raise ValueError("at least one entity type is required")
        if any(not t.replace("_", "").isalnum() or len(t) > 24 for t in cleaned):
            raise ValueError("entity types are short names of letters, digits and underscores")
        return cleaned


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    settings: GraphSettings | None = None


class ProjectUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    settings: GraphSettings | None = None


class ProjectOut(ApiModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    role: str
    settings: GraphSettings
    graph_version: int
    created_at: datetime


class MemberOut(ApiModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: str
    joined_at: datetime


class MemberAdd(StrictModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=120)
    role: Literal["owner", "editor", "viewer"] = "viewer"


class MemberAdded(ApiModel):
    member: MemberOut
    temporary_password: str | None = Field(
        default=None, description="Set only when the account was created by this call. Shown once."
    )


class MemberUpdate(StrictModel):
    role: Literal["owner", "editor", "viewer"]


class AuditEventOut(ApiModel):
    id: uuid.UUID
    action: str
    target_type: str
    target_id: str | None
    details: dict[str, Any]
    actor: str | None = Field(default=None, description="Name of the person or API key.")
    created_at: datetime
