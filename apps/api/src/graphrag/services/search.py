"""Questions over the graph: local, global and hybrid search with citations.

**Local** starts from the entities a question is about (names written in it, entities whose
embedding is close to it, entities in the passages that match it best), walks the graph a few
hops, and gathers the passages those entities and relations came from. Passages are scored on
four signals (vector similarity, keyword rank, how many seed entities they mention, how many
chosen edges they evidence) and the best few become numbered sources.

**Global** answers questions about the corpus as a whole. Every community report of one level
is scored for the question; the relevant ones are mapped to points ("what in this report helps
answer?"), and the best points are reduced into one answer that cites the communities.

**Hybrid** does both and answers from the passages plus the strongest community points.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from graphrag.core import metrics
from graphrag.core.errors import NotFoundError
from graphrag.core.logging import get_logger
from graphrag.core.text import content_terms
from graphrag.graph.search import compose
from graphrag.graph.search.contracts import Answer, ContextItem, Point
from graphrag.graph.search.keyword import keyword_query
from graphrag.models import Community, Project, QueryLog
from graphrag.repositories.chunks import ChunkRepository, ChunkRow
from graphrag.repositories.communities import CommunityRepository
from graphrag.repositories.graph import GraphRepository
from graphrag.repositories.queries import QueryLogRepository
from graphrag.schemas.search import (
    CommunityUse,
    EdgeUse,
    NodeUse,
    QueryRequest,
    QueryResponse,
    QuerySummary,
    StepOut,
)
from graphrag.services.container import Container
from graphrag.services.principal import Principal

log = get_logger("graphrag.search")
MAX_SEEDS = 8
MAX_LEXICAL = 6
MAX_EXPANDED_NODES = 48
HOP_DECAY = 0.6
MIN_ENTITY_SIMILARITY = 0.12
MAP_CONCURRENCY = 4
MAX_COMMUNITIES = 24
HYBRID_COMMUNITIES = 3
GLOBAL_POINTS = 8
BROAD_SCORE = 30.0
# Lines every template report carries that answer nothing by themselves.
_BOILERPLATE = ("Key relationships", "It spans", "It breaks down")
GLOBAL_FLOOR = 0.25


@dataclass(slots=True)
class _Trace:
    steps: list[StepOut] = field(default_factory=list)
    _mark: float = field(default_factory=time.perf_counter)

    def step(self, name: str, detail: str, mode: str) -> None:
        now = time.perf_counter()
        elapsed = now - self._mark
        self._mark = now
        self.steps.append(StepOut(name=name, detail=detail, ms=round(elapsed * 1000, 1)))
        metrics.QUERY_STAGE.labels(mode, name).observe(elapsed)


@dataclass(slots=True)
class _Local:
    items: list[ContextItem] = field(default_factory=list)
    nodes: list[NodeUse] = field(default_factory=list)
    edges: list[EdgeUse] = field(default_factory=list)
    communities: list[CommunityUse] = field(default_factory=list)


@dataclass(slots=True)
class _Global:
    items: list[ContextItem] = field(default_factory=list)
    communities: list[CommunityUse] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # No report shared a word with the question, so the most central ones were used.
    broad: bool = False


class SearchService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.chunks = ChunkRepository(session)
        self.graph = GraphRepository(session)
        self.communities = CommunityRepository(session)
        self.logs = QueryLogRepository(session)

    # Public -----------------------------------------------------------------------------

    async def ask(
        self, project: Project, principal: Principal, request: QueryRequest
    ) -> QueryResponse:
        started = time.perf_counter()
        cache_key = self._cache_key(project, request)
        if request.cache and (cached := await self._cache_get(cache_key)) is not None:
            metrics.CACHE.labels("query", "hit").inc()
            return await self._store(project, principal, request, cached, started, cached=True)
        metrics.CACHE.labels("query", "miss").inc()
        payload = await self._answer(project, request)
        payload["steps"].append(
            {"name": "total", "detail": "", "ms": round((time.perf_counter() - started) * 1000, 1)}
        )
        if self.c.settings.query_cache_ttl_s:
            await self._cache_put(cache_key, payload)
        return await self._store(project, principal, request, payload, started, cached=False)

    async def history(
        self, project: Project, *, mode: str | None, limit: int, offset: int
    ) -> tuple[list[QuerySummary], int]:
        rows, total = await self.logs.page(project.id, mode=mode, limit=limit, offset=offset)
        return [QuerySummary.model_validate(r) for r in rows], total

    async def get(self, project: Project, query_id: uuid.UUID) -> QueryResponse:
        row = await self.logs.get(project.id, query_id)
        if row is None:
            raise NotFoundError("Query not found.")
        return self._response(row)

    # Pipeline ---------------------------------------------------------------------------

    async def _answer(self, project: Project, request: QueryRequest) -> dict[str, Any]:
        mode = request.mode
        trace = _Trace()
        embedder = self.c.embedders.get(str(project.id))
        qvec = await embedder.embed_query(request.question)
        trace.step(
            "embed", f"{self.c.embedders.spec.provider} embedding, {qvec.shape[0]} dimensions", mode
        )

        local = _Local()
        global_ = _Global()
        if mode in ("local", "hybrid"):
            local = await self._local(project, request, qvec, trace)
        if mode in ("global", "hybrid"):
            global_ = await self._global(
                project,
                request,
                qvec,
                trace,
                limit=HYBRID_COMMUNITIES if mode == "hybrid" else GLOBAL_POINTS,
            )

        items = [*local.items, *global_.items]
        for n, item in enumerate(items, start=1):
            item.n = n
        answer = await self._compose(request.question, items, mode=mode, broad=global_.broad)
        answer.prompt_tokens += global_.prompt_tokens
        answer.completion_tokens += global_.completion_tokens
        trace.step(
            "answer", f"{answer.answerer}, {len(answer.cited)} of {len(items)} sources cited", mode
        )
        metrics.QUERIES.labels(mode).inc()

        communities = {c.id: c for c in [*global_.communities, *local.communities]}
        return {
            "answer": answer.text,
            "answerer": answer.answerer,
            "citations": [
                {
                    "n": item.n,
                    "kind": item.kind,
                    "id": item.id,
                    "label": item.label,
                    "snippet": _snippet(item.text),
                    "score": round(item.score, 4),
                    "cited": item.n in answer.cited,
                    "document_id": item.document_id,
                    "document_title": item.document_title,
                    "location": item.location,
                    "supports": list(item.chunk_ids),
                }
                for item in items
            ],
            "nodes": [n.model_dump(mode="json") for n in local.nodes],
            "edges": [e.model_dump(mode="json") for e in local.edges],
            "communities": [c.model_dump(mode="json") for c in communities.values()],
            "steps": [s.model_dump(mode="json") for s in trace.steps],
            "prompt_tokens": answer.prompt_tokens,
            "completion_tokens": answer.completion_tokens,
        }

    async def _compose(
        self, question: str, items: list[ContextItem], *, mode: str, broad: bool
    ) -> Answer:
        client = self.c.chat_client
        if not items:
            return Answer(compose.NO_ANSWER, "local")
        if client is None:
            if broad:
                return compose.digest_answer(items)
            if mode == "global":
                return compose.extractive_answer(
                    question, items, sentences=6, relative_floor=GLOBAL_FLOOR
                )
            return compose.extractive_answer(question, items, sentences=4)
        return await compose.model_answer(client, question, items, self.c.settings.llm_max_tokens)

    # Local ------------------------------------------------------------------------------

    async def _local(
        self, project: Project, request: QueryRequest, qvec: np.ndarray, trace: _Trace
    ) -> _Local:
        mode = request.mode
        dim = self.c.embedders.spec.dim
        wide = request.top_k * 4
        vector_hits = await self.chunks.vector_candidates(
            project_id=project.id, dim=dim, query=qvec, limit=wide
        )
        keyword_hits = await self._keyword(project, request.question, wide)
        trace.step(
            "passages", f"{len(vector_hits)} by vector, {len(keyword_hits)} by keyword", mode
        )

        seeds = await self._seeds(project, request.question, qvec, vector_hits, dim)
        trace.step(
            "seeds",
            ", ".join(name for name, _ in list(seeds.names.items())[:4]) or "no entities matched",
            mode,
        )
        nodes, relations = await self._expand(project, seeds.scores, request.hops)
        trace.step(
            "expand",
            f"{len(nodes)} entities and {len(relations)} relations within {request.hops} hop(s)",
            mode,
        )

        ranked = await self._rank_chunks(
            project, qvec, dim, vector_hits, keyword_hits, seeds.scores, relations
        )
        top = ranked[: request.top_k]
        rows = await self.chunks.hydrate(project.id, [c for c, _ in top])
        items = [_chunk_item(rows[chunk_id], score) for chunk_id, score in top if chunk_id in rows]
        trace.step("rank", f"{len(ranked)} candidates, {len(items)} kept", mode)

        node_rows = await self.graph.get_entities(project.id, list(nodes))
        node_uses = [
            NodeUse(
                id=i,
                name=node_rows[i].name,
                type=node_rows[i].type,
                role="seed" if i in seeds.scores else "neighbor",
                score=round(score, 4),
                degree=node_rows[i].degree,
            )
            for i, score in sorted(nodes.items(), key=lambda kv: -kv[1])
            if i in node_rows
        ]
        edge_rows = await self.graph.relations_among(project.id, list(nodes))
        edges = [
            EdgeUse(
                id=r.id,
                source_id=r.source_id,
                target_id=r.target_id,
                predicate=r.predicate,
                weight=r.weight,
            )
            for r in edge_rows
        ]
        placed = await self.graph.community_levels_of(project.id, list(seeds.scores), 1)
        scores: dict[uuid.UUID, float] = defaultdict(float)
        for entity_id, community in placed.items():
            scores[community.id] += seeds.scores[entity_id]
        communities = [
            CommunityUse(id=c.id, level=c.level, title=c.title, score=round(scores[c.id], 4))
            for c in sorted(
                {c.id: c for c in placed.values()}.values(), key=lambda c: -scores[c.id]
            )[:3]
        ]
        return _Local(items, node_uses, edges, communities)

    async def _keyword(
        self, project: Project, question: str, limit: int
    ) -> list[tuple[uuid.UUID, float]]:
        query = keyword_query(question)
        if query is None:
            return []
        return await self.chunks.keyword_candidates(
            project_id=project.id, tsquery=query, limit=limit
        )

    @dataclass(slots=True)
    class _Seeds:
        scores: dict[uuid.UUID, float]
        names: dict[str, float]

    async def _seeds(
        self,
        project: Project,
        question: str,
        qvec: np.ndarray,
        vector_hits: list[tuple[uuid.UUID, float]],
        dim: int,
    ) -> _Seeds:
        scores: dict[uuid.UUID, float] = {}
        for entity in await self.graph.lexical_matches(project.id, question, MAX_LEXICAL):
            scores[entity.id] = 1.0
        for entity_id, similarity in await self.graph.vector_entities(
            project.id, dim, qvec, MAX_SEEDS
        ):
            if similarity >= MIN_ENTITY_SIMILARITY:
                scores[entity_id] = max(
                    scores.get(entity_id, 0.0), round(0.3 + 0.7 * similarity, 4)
                )
        # Entities in the best matching passages: what the question is probably about even
        # when it does not name them.
        best = [chunk_id for chunk_id, _ in vector_hits[:3]]
        for _, entity_id in await self.graph.entities_in_chunks(project.id, best):
            scores.setdefault(entity_id, 0.35)
        top = dict(sorted(scores.items(), key=lambda kv: -kv[1])[:MAX_SEEDS])
        rows = await self.graph.get_entities(project.id, list(top))
        return self._Seeds(top, {rows[i].name: s for i, s in top.items() if i in rows})

    async def _expand(
        self, project: Project, seeds: dict[uuid.UUID, float], hops: int
    ) -> tuple[dict[uuid.UUID, float], list[Any]]:
        nodes = dict(seeds)
        relations: dict[uuid.UUID, Any] = {}
        frontier = set(seeds)
        for depth in range(1, hops + 1):
            if not frontier or len(nodes) >= MAX_EXPANDED_NODES:
                break
            found = await self.graph.relations_of(project.id, frontier, limit=40 * depth)
            reached: set[uuid.UUID] = set()
            for relation in found:
                for here, there in (
                    (relation.source_id, relation.target_id),
                    (relation.target_id, relation.source_id),
                ):
                    if here in frontier and len(nodes) < MAX_EXPANDED_NODES:
                        relations[relation.id] = relation
                        if there not in nodes:
                            nodes[there] = round(nodes[here] * HOP_DECAY, 4)
                            reached.add(there)
            frontier = reached
        return nodes, list(relations.values())

    async def _rank_chunks(
        self,
        project: Project,
        qvec: np.ndarray,
        dim: int,
        vector_hits: list[tuple[uuid.UUID, float]],
        keyword_hits: list[tuple[uuid.UUID, float]],
        seeds: dict[uuid.UUID, float],
        relations: list[Any],
    ) -> list[tuple[uuid.UUID, float]]:
        mentions = await self.graph.mentions_of(project.id, list(seeds))
        evidence = await self.graph.evidence_for(project.id, [r.id for r in relations])
        entity_cover: dict[uuid.UUID, float] = defaultdict(float)
        for entity_id, chunk_id, _ in mentions:
            entity_cover[chunk_id] += seeds[entity_id]
        edge_cover: dict[uuid.UUID, int] = defaultdict(int)
        for item in evidence:
            edge_cover[item.chunk_id] += 1
        candidates = {
            *[c for c, _ in vector_hits],
            *[c for c, _ in keyword_hits],
            *entity_cover,
            *edge_cover,
        }
        # One similarity for every candidate, whichever signal found it.
        vectors = await self.chunks.embeddings(project.id, list(candidates), dim)
        similarity = {c: float(np.dot(v, qvec)) for c, v in vectors.items()}
        top_keyword = max((r for _, r in keyword_hits), default=0.0) or 1.0
        keyword = {c: r / top_keyword for c, r in keyword_hits}
        scored = []
        for chunk_id in candidates:
            score = (
                0.45 * max(0.0, similarity.get(chunk_id, 0.0))
                + 0.20 * keyword.get(chunk_id, 0.0)
                + 0.25 * min(1.0, entity_cover.get(chunk_id, 0.0))
                + 0.10 * min(1.0, edge_cover.get(chunk_id, 0) / 2)
            )
            scored.append((chunk_id, round(score, 4)))
        return sorted(scored, key=lambda row: (-row[1], str(row[0])))

    # Global -----------------------------------------------------------------------------

    async def _global(
        self,
        project: Project,
        request: QueryRequest,
        qvec: np.ndarray,
        trace: _Trace,
        *,
        limit: int,
    ) -> _Global:
        mode = request.mode
        levels = await self.communities.level_counts(project.id)
        if not levels:
            trace.step("communities", "no communities yet: run a build", mode)
            return _Global()
        deepest = levels[-1][0]
        level = min(request.level if request.level is not None else 1, deepest)
        candidates = await self.communities.at_level(project.id, level)
        similarity = await self.communities.vector_rank(
            project.id, self.c.embedders.spec.dim, qvec, [c.id for c in candidates]
        )
        terms = set(content_terms(request.question))
        relevance: list[tuple[float, Community]] = []
        for community in candidates:
            report_terms = set(content_terms(f"{community.title} {community.summary}"))
            lexical = len(terms & report_terms) / max(1, len(terms))
            relevance.append(
                (0.5 * max(0.0, similarity.get(community.id, 0.0)) + 0.5 * lexical, community)
            )
        relevance.sort(key=lambda row: (-row[0], row[1].level, row[1].ordinal))
        chosen = relevance[:MAX_COMMUNITIES]
        trace.step(
            "communities", f"{len(chosen)} of {len(candidates)} reports at level {level}", mode
        )

        gate = asyncio.Semaphore(MAP_CONCURRENCY)
        result = _Global()

        async def one(score: float, community: Community) -> tuple[Community, float, list[Point]]:
            item = _report_item(community, score)
            client = self.c.chat_client
            async with gate:
                if client is None:
                    return community, score, compose.local_points(request.question, item)
                points, prompt, completion = await compose.model_points(
                    client, request.question, item, self.c.settings.llm_max_tokens
                )
                result.prompt_tokens += prompt
                result.completion_tokens += completion
                return community, score, points

        mapped = await asyncio.gather(*(one(s, c) for s, c in chosen))
        useful = [(c, s, [p for p in pts if p.score > 0]) for c, s, pts in mapped]
        useful = [row for row in useful if row[2]]
        if not useful:
            # A broad question ("what are the main themes?") shares no words with any report:
            # answer from the most central communities instead of from nothing.
            useful = [
                (c, s, [Point(text, BROAD_SCORE) for text in _opening(c)])
                for s, c in sorted(relevance, key=lambda row: -row[1].rank)[:limit]
            ]
            result.broad = True
            trace.step("map", f"no report matched; the {len(useful)} most central ones used", mode)
        else:
            trace.step("map", f"{len(useful)} reports contributed points", mode)

        ranked = sorted(useful, key=lambda row: (-max(p.score for p in row[2]), row[0].ordinal))
        used = ranked[:limit]
        for community, score, points in used:
            best = sorted(points, key=lambda p: -p.score)[:3]
            item = _report_item(community, max(score, best[0].score / 100))
            item.text = " ".join(p.text.rstrip() for p in best)
            result.items.append(item)
            result.communities.append(
                CommunityUse(
                    id=community.id,
                    level=community.level,
                    title=community.title,
                    score=round(best[0].score / 100, 4),
                    points=[p.text for p in best],
                )
            )
        trace.step("reduce", f"{len(used)} communities kept, best points first", mode)
        return result

    # Persistence and cache --------------------------------------------------------------

    def _cache_key(self, project: Project, request: QueryRequest) -> str:
        digest = hashlib.sha256(
            orjson.dumps(
                [
                    request.mode,
                    " ".join(request.question.lower().split()),
                    request.top_k,
                    request.hops,
                    request.level,
                    self.c.extractor.name,
                ]
            )
        ).hexdigest()
        return f"q:{project.id}:{project.graph_version}:{digest}"

    async def _cache_get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self.c.redis.get(key)
        except Exception:
            return None
        return orjson.loads(raw) if raw else None

    async def _cache_put(self, key: str, payload: dict[str, Any]) -> None:
        try:
            await self.c.redis.set(
                key, orjson.dumps(payload, default=str), ex=self.c.settings.query_cache_ttl_s
            )
        except Exception:
            log.warning("query_cache_write_failed")

    async def _store(
        self,
        project: Project,
        principal: Principal,
        request: QueryRequest,
        payload: dict[str, Any],
        started: float,
        *,
        cached: bool,
    ) -> QueryResponse:
        latency = int((time.perf_counter() - started) * 1000)
        row = await self.logs.add(
            QueryLog(
                project_id=project.id,
                user_id=principal.user_id,
                api_key_id=principal.api_key_id,
                mode=request.mode,
                question=request.question if self.c.settings.query_log_text else "",
                answer=payload["answer"],
                answerer=payload["answerer"],
                result=_jsonable(payload),
                citation_count=sum(1 for c in payload["citations"] if c["cited"]),
                latency_ms=latency,
                prompt_tokens=payload["prompt_tokens"],
                completion_tokens=payload["completion_tokens"],
                cached=cached,
            )
        )
        await self.session.commit()
        return self._response(row)

    @staticmethod
    def _response(row: QueryLog) -> QueryResponse:
        result = row.result
        return QueryResponse.model_validate(
            {
                "id": row.id,
                "mode": row.mode,
                "question": row.question,
                "answer": row.answer,
                "answerer": row.answerer,
                "citations": result.get("citations", []),
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", []),
                "communities": result.get("communities", []),
                "steps": result.get("steps", []),
                "latency_ms": row.latency_ms,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "cached": row.cached,
                "created_at": row.created_at or datetime.now(UTC),
            }
        )


def _opening(community: Community) -> list[str]:
    """The first two sentences of a report that say something (not the headcount)."""
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", community.summary) if len(s.strip()) > 30
    ]
    return [s for s in sentences if not s.startswith(_BOILERPLATE)][:2]


def _jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = orjson.loads(orjson.dumps(payload, default=str))
    return out


def _snippet(text: str, limit: int = 320) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\N{HORIZONTAL ELLIPSIS}"


def _chunk_item(row: ChunkRow, score: float) -> ContextItem:
    return ContextItem(
        n=0,
        kind="chunk",
        id=str(row.id),
        label=f"{row.document_title}, {row.location}",
        text=row.text,
        score=score,
        document_id=str(row.document_id),
        document_title=row.document_title,
        location=row.location,
    )


def _report_item(community: Community, score: float) -> ContextItem:
    findings = " ".join(
        f"{f.get('explanation', '')}".strip() or f"{f['summary']}." for f in community.findings
    )
    narrative = " ".join(
        s for s in re.split(r"(?<=[.!?])\s+", community.summary) if not s.startswith(_BOILERPLATE)
    )
    chunk_ids = tuple(dict.fromkeys(c for f in community.findings for c in f.get("chunk_ids", [])))
    return ContextItem(
        n=0,
        kind="community",
        id=str(community.id),
        label=f"Community report: {community.title}",
        text=f"{narrative} {findings}",
        score=score,
        chunk_ids=chunk_ids,
    )
