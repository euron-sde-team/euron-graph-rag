"""The knowledge graph: entities, relations and the evidence that ties both to chunks."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from graphrag.db.base import Base, IdMixin, TimestampMixin
from graphrag.db.types import Embedding


class Entity(IdMixin, TimestampMixin, Base):
    """A node. `key` is the normalized name: one entity per (project, key), so extraction
    from many documents converges on the same row instead of creating duplicates."""

    __tablename__ = "entities"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    key: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(24))
    description: Mapped[str] = mapped_column(Text, default="")
    # Other surface forms seen in text or merged in by duplicate resolution.
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    mention_count: Mapped[int] = mapped_column(default=0)
    # Number of distinct neighbours and the sum of incident relation weights, both
    # maintained by the graph build; the explorer sizes nodes by degree.
    degree: Mapped[int] = mapped_column(default=0)
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[Any] = mapped_column(Embedding())
    embedding_dim: Mapped[int] = mapped_column(SmallInteger)


class EntityMention(Base):
    """An entity appears in a chunk: what links the graph back to the text it came from."""

    __tablename__ = "entity_mentions"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    surface: Mapped[str] = mapped_column(String(300))
    count: Mapped[int] = mapped_column(default=1)


class Relation(IdMixin, TimestampMixin, Base):
    """A directed edge. Unique per (source, target, predicate); repeated evidence raises
    `weight` instead of creating parallel edges."""

    __tablename__ = "relations"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    predicate: Mapped[str] = mapped_column(String(48))
    description: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_count: Mapped[int] = mapped_column(default=1)


class RelationEvidence(Base):
    __tablename__ = "relation_evidence"

    relation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relations.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    quote: Mapped[str] = mapped_column(Text, default="")
