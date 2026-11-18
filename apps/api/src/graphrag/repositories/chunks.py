"""Chunks: written per document, browsed, hydrated for citations and searched two ways.

Vector search uses the HNSW index for the deployment's embedding width with iterative scans
(pgvector 0.8), so filtering by project does not starve the result list the way
post-filtering would. The width is a SQL literal taken from the supported set, never a
parameter: the planner must be able to match the partial index on every execution.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import (
    Float,
    String,
    bindparam,
    cast,
    delete,
    func,
    insert,
    literal_column,
    select,
    text,
)
from sqlalchemy.sql.elements import ColumnElement

from graphrag.core.ids import uuid7
from graphrag.db.types import SUPPORTED_DIMS, Embedding
from graphrag.ingestion.chunkers import ChunkDraft
from graphrag.models import Chunk, Document
from graphrag.repositories.base import Repository

_TUNE_HNSW = text(
    "SELECT set_config('hnsw.ef_search', :ef_search, true), "
    "set_config('hnsw.iterative_scan', 'relaxed_order', true)"
)
_ENGLISH: ColumnElement[Any] = literal_column("'english'::regconfig")


@dataclass(frozen=True, slots=True)
class ChunkRow:
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    ordinal: int
    heading: str
    location: str
    text: str
    token_count: int


class ChunkRepository(Repository):
    async def replace_for_document(
        self,
        *,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        drafts: Sequence[ChunkDraft],
        embeddings: np.ndarray,
        dim: int,
    ) -> list[uuid.UUID]:
        """Swap a document's chunks in one transaction; returns the new ids in order."""
        await self.session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        ids = [uuid7() for _ in drafts]
        if drafts:
            await self.session.execute(
                insert(Chunk),
                [
                    {
                        "id": ids[i],
                        "project_id": project_id,
                        "document_id": document_id,
                        "ordinal": d.ordinal,
                        "section_ordinal": d.section_ordinal,
                        "heading": d.heading,
                        "location": d.location,
                        "text": d.text,
                        "char_start": d.char_start,
                        "char_end": d.char_end,
                        "token_count": d.token_count,
                        "embedding": embeddings[i],
                        "embedding_dim": dim,
                    }
                    for i, d in enumerate(drafts)
                ],
            )
        return ids

    async def for_document(self, document_id: uuid.UUID) -> list[Chunk]:
        result = await self.session.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
        )
        return list(result.scalars())

    async def page(
        self, document_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[Chunk], int]:
        total = int(
            await self.session.scalar(select(func.count()).where(Chunk.document_id == document_id))
            or 0
        )
        result = await self.session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.ordinal)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total

    async def count(self, project_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(select(func.count()).where(Chunk.project_id == project_id))
            or 0
        )

    async def vector_candidates(
        self, *, project_id: uuid.UUID, dim: int, query: np.ndarray, limit: int
    ) -> list[tuple[uuid.UUID, float]]:
        if dim not in SUPPORTED_DIMS:
            raise ValueError(f"unsupported embedding width {dim}")
        await self.session.execute(_TUNE_HNSW, {"ef_search": str(max(40, limit * 2))})
        typed = cast(Chunk.embedding, Embedding(dim))
        distance = typed.op("<=>", return_type=Float)(
            bindparam("query_vector", value=query, type_=Embedding())
        )
        rows = (
            await self.session.execute(
                select(Chunk.id, (1 - distance).label("score"))
                .where(
                    Chunk.project_id == project_id,
                    Chunk.embedding_dim == literal_column(str(dim)),
                )
                .order_by(distance)
                .limit(limit)
            )
        ).all()
        # relaxed_order may return near-ties out of order; fusion needs the true order.
        return sorted(((r.id, float(r.score)) for r in rows), key=lambda item: -item[1])

    async def keyword_candidates(
        self, *, project_id: uuid.UUID, tsquery: str, limit: int
    ) -> list[tuple[uuid.UUID, float]]:
        query = func.to_tsquery(_ENGLISH, bindparam("tsquery", value=tsquery, type_=String))
        rank = func.ts_rank_cd(Chunk.tsv, query, 32)
        rows = (
            await self.session.execute(
                select(Chunk.id, rank.label("rank"))
                .where(Chunk.project_id == project_id, Chunk.tsv.op("@@")(query))
                .order_by(rank.desc(), Chunk.id)
                .limit(limit)
            )
        ).all()
        return [(r.id, float(r.rank)) for r in rows]

    async def hydrate(
        self, project_id: uuid.UUID, ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ChunkRow]:
        if not ids:
            return {}
        result = await self.session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Document.title.label("document_title"),
                Chunk.ordinal,
                Chunk.heading,
                Chunk.location,
                Chunk.text,
                Chunk.token_count,
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.project_id == project_id, Chunk.id.in_(list(ids)))
        )
        return {
            row.id: ChunkRow(
                row.id,
                row.document_id,
                row.document_title,
                row.ordinal,
                row.heading,
                row.location,
                row.text,
                row.token_count,
            )
            for row in result.all()
        }

    async def embeddings(
        self, project_id: uuid.UUID, ids: Sequence[uuid.UUID], dim: int
    ) -> dict[uuid.UUID, np.ndarray]:
        """Stored vectors of the given chunks (only those of the current width)."""
        if not ids:
            return {}
        result = await self.session.execute(
            select(Chunk.id, Chunk.embedding).where(
                Chunk.project_id == project_id,
                Chunk.id.in_(list(ids)),
                Chunk.embedding_dim == dim,
            )
        )
        return {row.id: np.asarray(row.embedding, dtype=np.float32) for row in result.all()}
