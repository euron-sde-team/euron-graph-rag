from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from graphrag.db.base import Base, IdMixin, TimestampMixin


class Document(IdMixin, TimestampMixin, Base):
    """One source in a project: an uploaded file, a fetched URL or a block of text."""

    __tablename__ = "documents"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # Stable, caller-chosen name (unique per project); API clients refer to documents by it.
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(8))
    source_uri: Mapped[str | None] = mapped_column(String(2048))
    kind: Mapped[str | None] = mapped_column(String(8))
    mime_type: Mapped[str | None] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(400))
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", default=dict)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    # Pipeline position while the status is queued or processing (models.enums.Stage).
    stage: Mapped[str] = mapped_column(String(16), default="queued")
    section_count: Mapped[int] = mapped_column(default=0)
    token_count: Mapped[int] = mapped_column(default=0)
    chunk_count: Mapped[int] = mapped_column(default=0)
    entity_count: Mapped[int] = mapped_column(default=0)
    relation_count: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    parsed_at: Mapped[datetime | None]
    extracted_at: Mapped[datetime | None]


class DocumentSection(IdMixin, Base):
    """A page or a section exactly as parsed; chunks derive from these without parsing again."""

    __tablename__ = "document_sections"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(300))
    # [{"text": "...", "level": 2 | null}]: headings keep their level so chunkers can build
    # heading paths without parsing again.
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(default=0)
