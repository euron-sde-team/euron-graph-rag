from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Computed, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from graphrag.db.base import Base, IdMixin
from graphrag.db.types import Embedding


class Chunk(IdMixin, Base):
    """A passage of a document: the unit of citation, of vector search and of extraction."""

    __tablename__ = "chunks"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    section_ordinal: Mapped[int]
    heading: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int]
    char_end: Mapped[int]
    token_count: Mapped[int]
    # Untyped vector column: deployments with different embedding widths share one schema,
    # and each supported width has its own partial HNSW index (see the initial migration).
    embedding: Mapped[Any] = mapped_column(Embedding())
    embedding_dim: Mapped[int] = mapped_column(SmallInteger)
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(heading, '') || ' ' || text)", persisted=True),
    )
