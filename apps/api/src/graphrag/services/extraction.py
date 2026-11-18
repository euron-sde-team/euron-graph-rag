"""Extraction: turn a document's chunks into entities, relations and mentions.

The extractor sees all chunks of one document at once (the rule extractor votes on entity
types across the document), then the result is written in one transaction:

- every entity name is looked up in the project's alias index, so a name seen before lands
  on its existing row; unseen names become new entities with an embedding;
- each (entity, chunk) pair becomes a mention and each relation a piece of evidence tied to
  the chunk whose sentence stated it, which is what every citation is built from;
- counts, weights and degrees are then rederived, never incremented, so re-running a
  document replaces its contribution instead of doubling it.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete

from graphrag.core import metrics
from graphrag.core.errors import AppError
from graphrag.core.logging import get_logger
from graphrag.graph.extraction.contracts import ChunkExtraction, ChunkInput
from graphrag.graph.names import entity_key
from graphrag.models import Entity, EntityMention, Project, RelationEvidence
from graphrag.models.enums import JobStatus, Stage
from graphrag.repositories.chunks import ChunkRepository
from graphrag.repositories.documents import DocumentRepository
from graphrag.repositories.graph import (
    EvidenceRow,
    GraphRepository,
    MentionRow,
    NewEntity,
)
from graphrag.schemas.projects import GraphSettings
from graphrag.services.builds import BuildService, Outcome, project_settings
from graphrag.services.container import Container

log = get_logger("graphrag.extraction")
DESCRIPTION_LIMIT = 480


def _describes(name: str, sentence: str) -> int:
    """How well a sentence introduces an entity: one that opens with the name, and is neither
    a fragment nor a paragraph, reads like a definition."""
    if not sentence:
        return 0
    opens = sentence.lower().startswith(name.lower()) or sentence.lower().startswith(
        f"the {name.lower()}"
    )
    return (2 if opens else 0) + (1 if 40 <= len(sentence) <= 240 else 0)


@dataclass(slots=True)
class _Aggregate:
    name: str
    type: str
    description: str
    votes: Counter[str]


class ExtractionService:
    def __init__(self, container: Container) -> None:
        self.c = container

    async def run(self, document_id: uuid.UUID, *, final_attempt: bool) -> Outcome:
        async with self.c.db.session() as session:
            document = await DocumentRepository(session).get_for_update(document_id)
            if document is None or document.status == JobStatus.READY:
                return Outcome.DONE
            project = await session.get(Project, document.project_id)
            if project is None:
                return Outcome.DONE
            document.stage = Stage.EXTRACTING
            document.status = JobStatus.PROCESSING
            settings = project_settings(project)
            chunks = await ChunkRepository(session).for_document(document_id)
            inputs = [ChunkInput(c.text, c.heading) for c in chunks]
            chunk_ids = [c.id for c in chunks]
            project_id = project.id
            await session.commit()

        extractor = self.c.extractor
        started = time.perf_counter()
        try:
            results = await extractor.extract(inputs, settings.entity_types) if inputs else []
        except AppError as exc:
            return await self._fail(document_id, exc.message, final_attempt, extractor.name)
        except Exception:
            log.exception("extraction_error", document_id=str(document_id))
            return await self._fail(
                document_id,
                "Extraction failed. Try reprocessing the document.",
                final_attempt,
                extractor.name,
            )

        try:
            counts = await self._persist(project_id, document_id, chunk_ids, results, settings)
        except Exception:
            log.exception("extraction_write_error", document_id=str(document_id))
            return await self._fail(
                document_id,
                "The graph could not be updated. Try reprocessing.",
                final_attempt,
                extractor.name,
            )
        elapsed = time.perf_counter() - started
        metrics.EXTRACTIONS.labels(extractor.name, "ready").inc()
        metrics.EXTRACTION_DURATION.labels(extractor.name).observe(elapsed)
        log.info(
            "extracted",
            document_id=str(document_id),
            entities=counts[0],
            relations=counts[1],
            seconds=round(elapsed, 2),
        )
        return Outcome.DONE

    async def _fail(
        self, document_id: uuid.UUID, message: str, final_attempt: bool, extractor: str
    ) -> Outcome:
        metrics.EXTRACTIONS.labels(extractor, "failed" if final_attempt else "retry").inc()
        async with self.c.db.session() as session:
            await DocumentRepository(session).mark(
                document_id,
                status=JobStatus.FAILED if final_attempt else JobStatus.QUEUED,
                stage=Stage.QUEUED,
                error=message[:1000] if final_attempt else None,
            )
            await session.commit()
        return Outcome.DONE if final_attempt else Outcome.RETRY

    async def _persist(
        self,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_ids: list[uuid.UUID],
        results: list[ChunkExtraction],
        settings: GraphSettings,
    ) -> tuple[int, int]:
        embedder = self.c.embedders.get(str(project_id))
        dim = self.c.embedders.spec.dim

        # One aggregate per entity key across the whole document.
        aggregates: dict[str, _Aggregate] = {}
        for result in results:
            for hit in result.entities:
                key = entity_key(hit.name)
                if not key:
                    continue
                agg = aggregates.setdefault(key, _Aggregate(hit.name, hit.type, "", Counter()))
                agg.votes[hit.type] += hit.count
                if _describes(hit.name, hit.description) > _describes(agg.name, agg.description):
                    agg.description = hit.description
        for agg in aggregates.values():
            ranked = [(t, n) for t, n in agg.votes.most_common() if t != "OTHER"]
            agg.type = ranked[0][0] if ranked else "OTHER"

        async with self.c.db.session() as session:
            graph = GraphRepository(session)
            documents = DocumentRepository(session)
            await graph.lock(project_id)
            document = await documents.get_for_update(document_id)
            project = await session.get(Project, project_id)
            if document is None or project is None:
                return 0, 0
            # Replace this document's earlier contribution.
            await session.execute(
                delete(EntityMention).where(EntityMention.document_id == document_id)
            )
            if chunk_ids:
                await session.execute(
                    delete(RelationEvidence).where(RelationEvidence.chunk_id.in_(chunk_ids))
                )

            index = await graph.alias_index(project_id)
            resolved = {key: index[key] for key in aggregates if key in index}
            fresh = [
                NewEntity(
                    a.name,
                    key,
                    a.type,
                    a.description[:DESCRIPTION_LIMIT],
                    np.zeros(dim, dtype=np.float32),
                )
                for key, a in aggregates.items()
                if key not in resolved
            ]
            if fresh:
                vectors = await embedder.embed_documents(
                    [f"{n.name}. {n.description}".strip() for n in fresh]
                )
                fresh = [
                    NewEntity(n.name, n.key, n.type, n.description, vectors[i])
                    for i, n in enumerate(fresh)
                ]
                resolved.update(await graph.add_entities(project_id, fresh, dim))
            await self._refresh_known(graph, project_id, aggregates, resolved)

            mentions: list[MentionRow] = []
            evidence: list[EvidenceRow] = []
            for chunk_id, result in zip(chunk_ids, results, strict=False):
                per_entity: dict[uuid.UUID, tuple[str, int]] = {}
                for hit in result.entities:
                    entity_id = resolved.get(entity_key(hit.name))
                    if entity_id is not None:
                        _, count = per_entity.get(entity_id, (hit.name, 0))
                        per_entity[entity_id] = (hit.name, count + hit.count)
                mentions.extend(
                    MentionRow(entity_id, chunk_id, document_id, surface[:300], count)
                    for entity_id, (surface, count) in per_entity.items()
                )
                for relation in result.relations:
                    source = resolved.get(entity_key(relation.source))
                    target = resolved.get(entity_key(relation.target))
                    if source is None or target is None or source == target:
                        continue
                    evidence.append(
                        EvidenceRow(
                            source,
                            target,
                            relation.predicate,
                            relation.description[:DESCRIPTION_LIMIT],
                            chunk_id,
                            relation.quote,
                        )
                    )
            await graph.add_mentions(project_id, mentions)
            await graph.add_evidence(project_id, evidence)
            await session.flush()
            await graph.recount(project_id)
            await graph.refresh_degrees(project_id)
            entity_total, relation_total = await graph.document_counts(document_id)
            document.entity_count = entity_total
            document.relation_count = relation_total
            document.stage = Stage.DONE
            document.status = JobStatus.READY
            document.error = None
            document.extracted_at = datetime.now(UTC)
            metrics.ENTITIES_WRITTEN.inc(len(aggregates))
            metrics.RELATIONS_WRITTEN.inc(len(evidence))
            builds = BuildService(self.c, session)
            await builds.graph_changed(project, document.created_by)
            await session.commit()
            await builds.dispatch_pending(project)
        return entity_total, relation_total

    @staticmethod
    async def _refresh_known(
        graph: GraphRepository,
        project_id: uuid.UUID,
        aggregates: dict[str, _Aggregate],
        resolved: dict[str, uuid.UUID],
    ) -> None:
        """Existing entities seen again: a vague type gets the specific one, and a short
        description is replaced by a fuller one."""
        known = await graph.get_entities(project_id, set(resolved.values()))
        for key, agg in aggregates.items():
            entity: Entity | None = known.get(resolved[key])
            if entity is None:
                continue
            if entity.type == "OTHER" and agg.type != "OTHER":
                entity.type = agg.type
            if len(entity.description) < 60 and len(agg.description) > len(entity.description):
                entity.description = agg.description[:DESCRIPTION_LIMIT]
