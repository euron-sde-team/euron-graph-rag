"""The knowledge graph: entities, mentions, relations and their evidence.

Counts (`mention_count`, `evidence_count`, `weight`) are derived from the mention and evidence
rows by `recount`, never incremented in place, so re-running a document, deleting it or
merging entities always leaves them consistent.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import (
    Float,
    bindparam,
    cast,
    delete,
    func,
    insert,
    literal_column,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased

from graphrag.core.ids import uuid7
from graphrag.db.types import SUPPORTED_DIMS, Embedding
from graphrag.models import (
    Chunk,
    Community,
    CommunityMember,
    Document,
    Entity,
    EntityMention,
    Relation,
    RelationEvidence,
)
from graphrag.repositories.base import Repository

GENERIC_PREDICATE = "RELATED_TO"
GENERIC_WEIGHT = 0.4


@dataclass(frozen=True, slots=True)
class NewEntity:
    name: str
    key: str
    type: str
    description: str
    embedding: np.ndarray


@dataclass(frozen=True, slots=True)
class MentionRow:
    entity_id: uuid.UUID
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    surface: str
    count: int


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    source_id: uuid.UUID
    target_id: uuid.UUID
    predicate: str
    description: str
    chunk_id: uuid.UUID
    quote: str


@dataclass(frozen=True, slots=True)
class EntityFilter:
    query: str | None = None
    types: Sequence[str] = ()
    community_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    min_degree: int = 0


class GraphRepository(Repository):
    # Entities ---------------------------------------------------------------------------

    async def alias_index(self, project_id: uuid.UUID) -> dict[str, uuid.UUID]:
        """Every known name key (primary and merged aliases) of the project, by entity id."""
        from graphrag.graph.names import entity_key

        rows = await self.session.execute(
            select(Entity.id, Entity.key, Entity.aliases).where(Entity.project_id == project_id)
        )
        index: dict[str, uuid.UUID] = {}
        for entity_id, key, aliases in rows.all():
            index[key] = entity_id
            for alias in aliases or []:
                index.setdefault(entity_key(alias), entity_id)
        return index

    async def get_entities(
        self, project_id: uuid.UUID, ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, Entity]:
        if not ids:
            return {}
        result = await self.session.execute(
            select(Entity).where(Entity.project_id == project_id, Entity.id.in_(list(ids)))
        )
        return {e.id: e for e in result.scalars()}

    async def get_entity(self, project_id: uuid.UUID, entity_id: uuid.UUID) -> Entity | None:
        return (await self.get_entities(project_id, [entity_id])).get(entity_id)

    async def add_entities(
        self, project_id: uuid.UUID, rows: Sequence[NewEntity], dim: int
    ) -> dict[str, uuid.UUID]:
        ids = {row.key: uuid7() for row in rows}
        if rows:
            await self.session.execute(
                insert(Entity),
                [
                    {
                        "id": ids[row.key],
                        "project_id": project_id,
                        "name": row.name,
                        "key": row.key,
                        "type": row.type,
                        "description": row.description,
                        "aliases": [],
                        "mention_count": 0,
                        "embedding": row.embedding,
                        "embedding_dim": dim,
                    }
                    for row in rows
                ],
            )
        return ids

    async def add_mentions(self, project_id: uuid.UUID, rows: Sequence[MentionRow]) -> None:
        if not rows:
            return
        statement = pg_insert(EntityMention).values(
            [
                {
                    "entity_id": r.entity_id,
                    "chunk_id": r.chunk_id,
                    "project_id": project_id,
                    "document_id": r.document_id,
                    "surface": r.surface,
                    "count": r.count,
                }
                for r in rows
            ]
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["entity_id", "chunk_id"],
                set_={"count": statement.excluded.count, "surface": statement.excluded.surface},
            )
        )

    async def add_evidence(self, project_id: uuid.UUID, rows: Sequence[EvidenceRow]) -> int:
        """Relations are unique per (source, target, predicate): evidence for an existing
        edge attaches to it. Returns how many distinct relations the rows touched."""
        touched: set[uuid.UUID] = set()
        existing: dict[tuple[uuid.UUID, uuid.UUID, str], uuid.UUID] = {}
        pairs = {(r.source_id, r.target_id, r.predicate) for r in rows}
        if pairs:
            found = await self.session.execute(
                select(
                    Relation.id, Relation.source_id, Relation.target_id, Relation.predicate
                ).where(
                    Relation.project_id == project_id,
                    Relation.source_id.in_({p[0] for p in pairs}),
                    Relation.target_id.in_({p[1] for p in pairs}),
                )
            )
            existing = {(r.source_id, r.target_id, r.predicate): r.id for r in found.all()}
        created: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        for row in rows:
            key = (row.source_id, row.target_id, row.predicate)
            relation_id = existing.get(key)
            if relation_id is None:
                relation_id = uuid7()
                existing[key] = relation_id
                created.append(
                    {
                        "id": relation_id,
                        "project_id": project_id,
                        "source_id": row.source_id,
                        "target_id": row.target_id,
                        "predicate": row.predicate,
                        "description": row.description,
                        "weight": GENERIC_WEIGHT if row.predicate == GENERIC_PREDICATE else 1.0,
                        "evidence_count": 1,
                    }
                )
            touched.add(relation_id)
            links.append(
                {
                    "relation_id": relation_id,
                    "chunk_id": row.chunk_id,
                    "project_id": project_id,
                    "quote": row.quote[:600],
                }
            )
        if created:
            await self.session.execute(insert(Relation), created)
        if links:
            statement = pg_insert(RelationEvidence).values(links)
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=["relation_id", "chunk_id"],
                    set_={"quote": statement.excluded.quote},
                )
            )
        return len(touched)

    async def recount(self, project_id: uuid.UUID) -> tuple[int, int]:
        """Rederive counts and weights from mentions and evidence, then drop entities that
        no chunk mentions and relations that no chunk supports. Returns (entities, relations)
        removed."""
        await self.session.execute(
            text(
                "UPDATE relations r SET evidence_count = e.n, "
                "weight = e.n * CASE WHEN r.predicate = :generic THEN :generic_weight ELSE 1.0 END "
                "FROM (SELECT relation_id, count(*) AS n FROM relation_evidence "
                "WHERE project_id = :p GROUP BY relation_id) e "
                "WHERE r.id = e.relation_id AND r.project_id = :p "
                "AND (r.evidence_count <> e.n OR r.weight IS NULL OR r.weight <> e.n * "
                "CASE WHEN r.predicate = :generic THEN :generic_weight ELSE 1.0 END)"
            ),
            {"p": project_id, "generic": GENERIC_PREDICATE, "generic_weight": GENERIC_WEIGHT},
        )
        gone_relations = await self.session.execute(
            delete(Relation).where(
                Relation.project_id == project_id,
                ~select(RelationEvidence.relation_id)
                .where(RelationEvidence.relation_id == Relation.id)
                .exists(),
            )
        )
        await self.session.execute(
            text(
                "UPDATE entities en SET mention_count = m.n FROM (SELECT entity_id, "
                "sum(count)::int AS n FROM entity_mentions WHERE project_id = :p "
                "GROUP BY entity_id) m WHERE en.id = m.entity_id AND en.project_id = :p "
                "AND en.mention_count <> m.n"
            ),
            {"p": project_id},
        )
        gone_entities = await self.session.execute(
            delete(Entity).where(
                Entity.project_id == project_id,
                ~select(EntityMention.entity_id)
                .where(EntityMention.entity_id == Entity.id)
                .exists(),
            )
        )
        return int(gone_entities.rowcount or 0), int(gone_relations.rowcount or 0)  # type: ignore[attr-defined]

    async def refresh_degrees(self, project_id: uuid.UUID) -> None:
        """Degree (distinct neighbours) and importance (weighted degree, boosted by mentions)."""
        await self.session.execute(
            text(
                "UPDATE entities en SET degree = COALESCE(d.n, 0), importance = "
                "COALESCE(d.w, 0) + 0.25 * ln(1 + en.mention_count) "
                "FROM entities base LEFT JOIN (SELECT id, count(DISTINCT other) AS n, "
                "sum(weight) AS w FROM (SELECT source_id AS id, target_id AS other, weight "
                "FROM relations WHERE project_id = :p UNION ALL SELECT target_id, source_id, "
                "weight FROM relations WHERE project_id = :p) edges "
                "GROUP BY id) d ON d.id = base.id "
                "WHERE en.id = base.id AND en.project_id = :p"
            ),
            {"p": project_id},
        )

    async def update_embedding(self, entity_id: uuid.UUID, embedding: np.ndarray, dim: int) -> None:
        await self.session.execute(
            update(Entity)
            .where(Entity.id == entity_id)
            .values(embedding=embedding, embedding_dim=dim)
        )

    async def merge(
        self, project_id: uuid.UUID, survivor_id: uuid.UUID, victim_ids: Sequence[uuid.UUID]
    ) -> None:
        """Fold `victim_ids` into `survivor_id`: mentions, relations and evidence move over
        (collapsing duplicates), names become aliases, then the victims are deleted."""
        survivor = await self.get_entity(project_id, survivor_id)
        victims = await self.get_entities(project_id, victim_ids)
        if survivor is None or not victims:
            return
        victim_list = list(victims)
        # Several victims can mention the same chunk: fold them per chunk before the upsert,
        # which cannot touch one row twice.
        await self.session.execute(
            text(
                "INSERT INTO entity_mentions (entity_id, chunk_id, project_id, document_id, "
                "surface, count) SELECT :survivor, chunk_id, project_id, document_id, "
                "min(surface), sum(count)::int FROM entity_mentions "
                "WHERE entity_id = ANY(:victims) GROUP BY chunk_id, project_id, document_id "
                "ON CONFLICT (entity_id, chunk_id) DO UPDATE "
                "SET count = entity_mentions.count + EXCLUDED.count"
            ).bindparams(
                bindparam("survivor", survivor_id, type_=PG_UUID(as_uuid=True)),
                bindparam("victims", victim_list, type_=ARRAY(PG_UUID(as_uuid=True))),
            )
        )
        await self.session.execute(
            delete(EntityMention).where(EntityMention.entity_id.in_(victim_list))
        )

        rows = await self.session.execute(
            select(Relation).where(
                Relation.project_id == project_id,
                or_(Relation.source_id.in_(victim_list), Relation.target_id.in_(victim_list)),
            )
        )
        for relation in rows.scalars().all():
            source = survivor_id if relation.source_id in victims else relation.source_id
            target = survivor_id if relation.target_id in victims else relation.target_id
            if source == target:
                await self.session.delete(relation)
                continue
            twin = await self.session.scalar(
                select(Relation.id).where(
                    Relation.source_id == source,
                    Relation.target_id == target,
                    Relation.predicate == relation.predicate,
                    Relation.id != relation.id,
                )
            )
            if twin is None:
                relation.source_id, relation.target_id = source, target
                continue
            await self.session.execute(
                text(
                    "INSERT INTO relation_evidence (relation_id, chunk_id, project_id, quote) "
                    "SELECT :twin, chunk_id, project_id, quote FROM relation_evidence "
                    "WHERE relation_id = :old ON CONFLICT DO NOTHING"
                ).bindparams(
                    bindparam("twin", twin, type_=PG_UUID(as_uuid=True)),
                    bindparam("old", relation.id, type_=PG_UUID(as_uuid=True)),
                )
            )
            await self.session.delete(relation)
        await self.session.flush()

        known = {survivor.name, *survivor.aliases}
        aliases = list(survivor.aliases)
        for victim in victims.values():
            for name in (victim.name, *victim.aliases):
                if name not in known:
                    known.add(name)
                    aliases.append(name)
        survivor.aliases = aliases
        survivor.description = _merge_descriptions(
            survivor.description, [v.description for v in victims.values()]
        )
        if survivor.type == "OTHER":
            survivor.type = next((v.type for v in victims.values() if v.type != "OTHER"), "OTHER")
        await self.session.execute(delete(Entity).where(Entity.id.in_(victim_list)))

    # Reads ------------------------------------------------------------------------------

    def _filtered(self, project_id: uuid.UUID, flt: EntityFilter) -> list[Any]:
        conditions: list[Any] = [Entity.project_id == project_id]
        if flt.types:
            conditions.append(Entity.type.in_(list(flt.types)))
        if flt.query:
            pattern = f"%{flt.query.strip()}%"
            conditions.append(or_(Entity.name.ilike(pattern), Entity.description.ilike(pattern)))
        if flt.min_degree:
            conditions.append(Entity.degree >= flt.min_degree)
        if flt.community_id:
            conditions.append(
                Entity.id.in_(
                    select(CommunityMember.entity_id).where(
                        CommunityMember.community_id == flt.community_id
                    )
                )
            )
        if flt.document_id:
            conditions.append(
                Entity.id.in_(
                    select(EntityMention.entity_id).where(
                        EntityMention.document_id == flt.document_id
                    )
                )
            )
        return conditions

    async def page(
        self, project_id: uuid.UUID, flt: EntityFilter, *, sort: str, limit: int, offset: int
    ) -> tuple[list[Entity], int]:
        conditions = self._filtered(project_id, flt)
        total = int(await self.session.scalar(select(func.count()).where(*conditions)) or 0)
        orders: dict[str, list[Any]] = {
            "name": [Entity.name],
            "mentions": [Entity.mention_count.desc(), Entity.name],
            "type": [Entity.type, Entity.name],
        }
        order = orders.get(sort, [Entity.importance.desc(), Entity.name])
        result = await self.session.execute(
            select(Entity)
            .where(*conditions)
            .order_by(*order, Entity.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total

    async def top(self, project_id: uuid.UUID, flt: EntityFilter, limit: int) -> list[Entity]:
        result = await self.session.execute(
            select(Entity)
            .where(*self._filtered(project_id, flt))
            .order_by(Entity.importance.desc(), Entity.name, Entity.id)
            .limit(limit)
        )
        return list(result.scalars())

    async def relations_among(
        self, project_id: uuid.UUID, entity_ids: Collection[uuid.UUID], *, min_weight: float = 0.0
    ) -> list[Relation]:
        if not entity_ids:
            return []
        ids = list(entity_ids)
        result = await self.session.execute(
            select(Relation)
            .where(
                Relation.project_id == project_id,
                Relation.source_id.in_(ids),
                Relation.target_id.in_(ids),
                Relation.weight >= min_weight,
            )
            .order_by(Relation.weight.desc(), Relation.id)
        )
        return list(result.scalars())

    async def relations_of(
        self, project_id: uuid.UUID, entity_ids: Collection[uuid.UUID], *, limit: int = 200
    ) -> list[Relation]:
        """Edges touching any of `entity_ids`, strongest first."""
        if not entity_ids:
            return []
        ids = list(entity_ids)
        result = await self.session.execute(
            select(Relation)
            .where(
                Relation.project_id == project_id,
                or_(Relation.source_id.in_(ids), Relation.target_id.in_(ids)),
            )
            .order_by(Relation.weight.desc(), Relation.id)
            .limit(limit)
        )
        return list(result.scalars())

    async def all_relations(self, project_id: uuid.UUID) -> list[Relation]:
        result = await self.session.execute(
            select(Relation).where(Relation.project_id == project_id)
        )
        return list(result.scalars())

    async def all_entities(self, project_id: uuid.UUID) -> list[Entity]:
        result = await self.session.execute(
            select(Entity).where(Entity.project_id == project_id).order_by(Entity.id)
        )
        return list(result.scalars())

    async def mentions_of(
        self, project_id: uuid.UUID, entity_ids: Collection[uuid.UUID]
    ) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
        """(entity id, chunk id, count) for the given entities."""
        if not entity_ids:
            return []
        result = await self.session.execute(
            select(
                EntityMention.entity_id,
                EntityMention.chunk_id,
                EntityMention.count.label("n"),
            ).where(
                EntityMention.project_id == project_id,
                EntityMention.entity_id.in_(list(entity_ids)),
            )
        )
        return [(r.entity_id, r.chunk_id, int(r.n)) for r in result.all()]

    async def entities_in_chunks(
        self, project_id: uuid.UUID, chunk_ids: Collection[uuid.UUID]
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """(chunk id, entity id) pairs for the given chunks."""
        if not chunk_ids:
            return []
        result = await self.session.execute(
            select(EntityMention.chunk_id, EntityMention.entity_id).where(
                EntityMention.project_id == project_id,
                EntityMention.chunk_id.in_(list(chunk_ids)),
            )
        )
        return [(r.chunk_id, r.entity_id) for r in result.all()]

    async def evidence_for(
        self, project_id: uuid.UUID, relation_ids: Collection[uuid.UUID]
    ) -> list[RelationEvidence]:
        if not relation_ids:
            return []
        result = await self.session.execute(
            select(RelationEvidence).where(
                RelationEvidence.project_id == project_id,
                RelationEvidence.relation_id.in_(list(relation_ids)),
            )
        )
        return list(result.scalars())

    async def mention_chunks(
        self, project_id: uuid.UUID, entity_id: uuid.UUID, limit: int
    ) -> list[tuple[Chunk, str, str, int]]:
        """Chunks that mention an entity: (chunk, document title, surface, count)."""
        result = await self.session.execute(
            select(Chunk, Document.title, EntityMention.surface, EntityMention.count)
            .join(EntityMention, EntityMention.chunk_id == Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(EntityMention.entity_id == entity_id, EntityMention.project_id == project_id)
            .order_by(EntityMention.count.desc(), Document.title, Chunk.ordinal)
            .limit(limit)
        )
        return [(c, t, s, n) for c, t, s, n in result.all()]

    async def top_for_document(
        self, project_id: uuid.UUID, document_id: uuid.UUID, limit: int
    ) -> list[tuple[Entity, int]]:
        total = func.sum(EntityMention.count)
        result = await self.session.execute(
            select(Entity, total)
            .join(EntityMention, EntityMention.entity_id == Entity.id)
            .where(Entity.project_id == project_id, EntityMention.document_id == document_id)
            .group_by(Entity.id)
            .order_by(total.desc(), Entity.name)
            .limit(limit)
        )
        return [(e, int(n)) for e, n in result.all()]

    async def lexical_matches(
        self, project_id: uuid.UUID, question: str, limit: int
    ) -> list[Entity]:
        """Entities whose name (or a known alias) appears inside the question text."""
        folded = question.lower()
        result = await self.session.execute(
            select(Entity)
            .where(
                Entity.project_id == project_id,
                func.length(Entity.key) >= 3,
                bindparam("q", value=folded).like(func.concat("%", Entity.key, "%")),
            )
            .order_by(func.length(Entity.key).desc(), Entity.importance.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def vector_entities(
        self, project_id: uuid.UUID, dim: int, query: np.ndarray, limit: int
    ) -> list[tuple[uuid.UUID, float]]:
        if dim not in SUPPORTED_DIMS:
            raise ValueError(f"unsupported embedding width {dim}")
        typed = cast(Entity.embedding, Embedding(dim))
        distance = typed.op("<=>", return_type=Float)(
            bindparam("query_vector", value=query, type_=Embedding())
        )
        rows = (
            await self.session.execute(
                select(Entity.id, (1 - distance).label("score"))
                .where(
                    Entity.project_id == project_id,
                    Entity.embedding_dim == literal_column(str(dim)),
                )
                .order_by(distance)
                .limit(limit)
            )
        ).all()
        return [(r.id, float(r.score)) for r in rows]

    async def type_counts(self, project_id: uuid.UUID) -> list[tuple[str, int]]:
        result = await self.session.execute(
            select(Entity.type, func.count())
            .where(Entity.project_id == project_id)
            .group_by(Entity.type)
            .order_by(func.count().desc(), Entity.type)
        )
        return [(t, int(n)) for t, n in result.all()]

    async def predicate_counts(
        self, project_id: uuid.UUID, limit: int = 12
    ) -> list[tuple[str, int]]:
        result = await self.session.execute(
            select(Relation.predicate, func.count())
            .where(Relation.project_id == project_id)
            .group_by(Relation.predicate)
            .order_by(func.count().desc(), Relation.predicate)
            .limit(limit)
        )
        return [(p, int(n)) for p, n in result.all()]

    async def counts(self, project_id: uuid.UUID) -> tuple[int, int]:
        entities = await self.session.scalar(
            select(func.count()).where(Entity.project_id == project_id)
        )
        relations = await self.session.scalar(
            select(func.count()).where(Relation.project_id == project_id)
        )
        return int(entities or 0), int(relations or 0)

    async def document_entity_ids(self, document_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self.session.execute(
            select(EntityMention.entity_id).where(EntityMention.document_id == document_id)
        )
        return set(result.scalars())

    async def document_counts(self, document_id: uuid.UUID) -> tuple[int, int]:
        entities = await self.session.scalar(
            select(func.count(func.distinct(EntityMention.entity_id))).where(
                EntityMention.document_id == document_id
            )
        )
        chunk_ids = select(Chunk.id).where(Chunk.document_id == document_id)
        relations = await self.session.scalar(
            select(func.count(func.distinct(RelationEvidence.relation_id))).where(
                RelationEvidence.chunk_id.in_(chunk_ids)
            )
        )
        return int(entities or 0), int(relations or 0)

    async def community_levels_of(
        self, project_id: uuid.UUID, entity_ids: Collection[uuid.UUID], level: int
    ) -> dict[uuid.UUID, Community]:
        """Each entity's community at `level` (or the deepest one above it when its branch
        stops splitting earlier)."""
        if not entity_ids:
            return {}
        member = aliased(CommunityMember)
        result = await self.session.execute(
            select(member.entity_id, Community)
            .join(Community, Community.id == member.community_id)
            .where(
                member.project_id == project_id,
                member.entity_id.in_(list(entity_ids)),
                Community.level <= level,
            )
            .order_by(member.entity_id, Community.level.desc())
        )
        chosen: dict[uuid.UUID, Community] = {}
        for entity_id, community in result.all():
            chosen.setdefault(entity_id, community)
        return chosen

    async def has_isolated(self, project_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(Entity.project_id == project_id, Entity.degree == 0)
            )
            or 0
        )


def _merge_descriptions(own: str, others: Sequence[str]) -> str:
    """Keep the survivor's description and add the first distinct one from a victim, so a
    merged entity reads as both sources described it, within a readable length."""
    parts = [own.strip()] if own.strip() else []
    for other in others:
        text_ = other.strip()
        if text_ and not any(text_ in p or p in text_ for p in parts):
            parts.append(text_)
    return " ".join(parts)[:480]


__all__ = [
    "EntityFilter",
    "EvidenceRow",
    "GraphRepository",
    "MentionRow",
    "NewEntity",
]
