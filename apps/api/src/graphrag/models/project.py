from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from graphrag.db.base import Base, IdMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, Base):
    """The unit of tenancy and one knowledge graph: documents, chunks, entities, relations,
    communities, queries and keys all belong to one project."""

    __tablename__ = "projects"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    # Extraction and community options (schemas.projects.GraphSettings), validated on write.
    settings: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Incremented whenever chunks, entities, relations or communities change. Cached query
    # results are keyed by it, so a change retires them without a scan.
    graph_version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Membership(Base):
    __tablename__ = "memberships"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
