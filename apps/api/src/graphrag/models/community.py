"""Communities: clusters of entities at several levels, each with a generated report."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from graphrag.db.base import Base, IdMixin, TimestampMixin
from graphrag.db.types import Embedding


class GraphBuild(IdMixin, TimestampMixin, Base):
    """One run of duplicate resolution, community detection and report generation."""

    __tablename__ = "graph_builds"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16))
    trigger: Mapped[str] = mapped_column(String(16))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Community(IdMixin, Base):
    """Level 0 is the coarsest partition; higher levels split it further. A community's
    `parent_id` is the community of the level above that contains it."""

    __tablename__ = "communities"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    build_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("graph_builds.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE")
    )
    level: Mapped[int] = mapped_column(SmallInteger)
    ordinal: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    # [{"summary": str, "explanation": str, "chunk_ids": [str]}]
    findings: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    entity_count: Mapped[int] = mapped_column(default=0)
    relation_count: Mapped[int] = mapped_column(default=0)
    rank: Mapped[float] = mapped_column(Float, default=0.0)
    reporter: Mapped[str] = mapped_column(String(32), default="local")
    embedding: Mapped[Any] = mapped_column(Embedding())
    embedding_dim: Mapped[int] = mapped_column(SmallInteger)


class CommunityMember(Base):
    __tablename__ = "community_members"

    community_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
