"""Community reports: a title, a summary and cited findings for each community.

`LocalReporter` writes them from templates over the community's own entities and relations,
so it is deterministic and offline. `LlmReporter` asks a model for the same structure from
the same inputs and falls back to the template when the reply cannot be parsed. Parent
communities are summarized from their children's reports plus their own strongest relations,
so a high level costs about as much as a low one.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from graphrag.ai.llm import ChatClient
from graphrag.core.logging import get_logger
from graphrag.graph.extraction.contracts import predicate_phrase
from graphrag.graph.extraction.llm import parse_reply

log = get_logger("graphrag.reports")
MAX_TITLE = 160
MAX_FINDINGS = 6
PROMPT_ENTITIES = 40
PROMPT_RELATIONS = 60

_TYPE_PLURALS = {
    "PERSON": "people",
    "ORGANIZATION": "organizations",
    "LOCATION": "locations",
    "PRODUCT": "products",
    "TECHNOLOGY": "technologies",
    "EVENT": "events",
    "CONCEPT": "concepts",
    "OTHER": "other entities",
}


@dataclass(frozen=True, slots=True)
class EntityBrief:
    id: str
    name: str
    type: str
    description: str
    importance: float
    degree: int


@dataclass(frozen=True, slots=True)
class RelationBrief:
    source: str
    target: str
    predicate: str
    description: str
    weight: float
    chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChildBrief:
    title: str
    summary: str


@dataclass(frozen=True, slots=True)
class ReportInput:
    level: int
    entities: Sequence[EntityBrief]
    relations: Sequence[RelationBrief]
    children: Sequence[ChildBrief] = ()


@dataclass(frozen=True, slots=True)
class Finding:
    summary: str
    explanation: str
    chunk_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "explanation": self.explanation,
            "chunk_ids": list(self.chunk_ids),
        }


@dataclass(slots=True)
class Report:
    title: str
    summary: str
    findings: list[Finding] = field(default_factory=list)


class Reporter(Protocol):
    name: str

    async def report(self, data: ReportInput) -> Report: ...


def _join_names(names: Sequence[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _top_entities(data: ReportInput, count: int) -> list[EntityBrief]:
    return sorted(data.entities, key=lambda e: (-e.importance, -e.degree, e.name))[:count]


def _top_relations(data: ReportInput, count: int) -> list[RelationBrief]:
    ranked = sorted(data.relations, key=lambda r: (-r.weight, r.source, r.target, r.predicate))
    # Prefer typed relations over the generic co-occurrence edge when there are enough.
    typed = [r for r in ranked if r.predicate != "RELATED_TO"]
    return (typed if len(typed) >= count else ranked)[:count]


def _sentence(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first[:limit].rstrip(" ,;:")


class LocalReporter:
    name = "local"

    async def report(self, data: ReportInput) -> Report:
        return template_report(data)


def template_report(data: ReportInput) -> Report:
    leaders = _top_entities(data, 3)
    title = _join_names([e.name for e in leaders])[:MAX_TITLE] or "Community"
    kinds = Counter(e.type for e in data.entities)
    breakdown = ", ".join(f"{n} {_TYPE_PLURALS.get(t, t.lower())}" for t, n in kinds.most_common(4))
    parts = [
        f"This community links {len(data.entities)} entities ({breakdown}) through "
        f"{len(data.relations)} relationships."
    ]
    if leaders and leaders[0].description:
        parts.append(
            f"{leaders[0].name} is the most connected: {_sentence(leaders[0].description)}."
        )
    facts = _top_relations(data, 3)
    if facts:
        rendered = "; ".join(
            f"{r.source} {predicate_phrase(r.predicate)} {r.target}" for r in facts
        )
        parts.append(f"Key relationships: {rendered}.")
    if data.children:
        parts.append(
            "It breaks down into " + _join_names([c.title for c in data.children[:4]]) + "."
        )
    findings = [
        Finding(
            f"{r.source} {predicate_phrase(r.predicate)} {r.target}",
            _sentence(r.description, 320)
            or f"{r.source} and {r.target} are linked in the sources.",
            r.chunk_ids,
        )
        for r in _top_relations(data, MAX_FINDINGS)
    ]
    return Report(title, " ".join(parts), findings)


SYSTEM = (
    "You write a short report about one community of a knowledge graph. Reply with one JSON "
    'object and nothing else: {"title": str, "summary": str, "findings": [{"summary": str, '
    '"explanation": str}]}. The title names what the community is about in at most ten words. '
    "The summary is two to four sentences. Give three to six findings; each states one fact in "
    "its summary and supports it in its explanation. Use only the entities, relationships and "
    "sub-community summaries provided."
)


def build_messages(data: ReportInput) -> list[dict[str, str]]:
    entities = "\n".join(
        f"- {e.name} ({e.type}): {_sentence(e.description, 160)}"
        for e in _top_entities(data, PROMPT_ENTITIES)
    )
    relations = "\n".join(
        f"- {r.source} {predicate_phrase(r.predicate)} {r.target}: {_sentence(r.description, 160)}"
        for r in _top_relations(data, PROMPT_RELATIONS)
    )
    children = "\n".join(f"- {c.title}: {_sentence(c.summary, 240)}" for c in data.children)
    user = f"Entities:\n{entities}\n\nRelationships:\n{relations}"
    if children:
        user += f"\n\nSub-communities:\n{children}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


class LlmReporter:
    def __init__(self, client: ChatClient, max_tokens: int) -> None:
        self.client = client
        self.name = f"{client.provider}:{client.default_model}"
        self._max_tokens = max_tokens

    async def report(self, data: ReportInput) -> Report:
        fallback = template_report(data)
        text, _ = await self.client.complete(build_messages(data), max_tokens=self._max_tokens)
        payload = parse_reply(text)
        if not payload or not isinstance(payload.get("title"), str) or not payload.get("summary"):
            log.warning("report_reply_unparsable", chars=len(text))
            return fallback
        evidence = _evidence_index(data)
        findings: list[Finding] = []
        for item in payload.get("findings") or []:
            if isinstance(item, dict) and item.get("summary"):
                summary = str(item["summary"])[:300]
                findings.append(
                    Finding(
                        summary,
                        str(item.get("explanation") or "")[:600],
                        _chunks_for(summary, evidence),
                    )
                )
        return Report(
            str(payload["title"]).strip()[:MAX_TITLE] or fallback.title,
            str(payload["summary"]).strip(),
            findings[:MAX_FINDINGS] or fallback.findings,
        )


def _evidence_index(data: ReportInput) -> list[tuple[str, str, tuple[str, ...]]]:
    return [(r.source.lower(), r.target.lower(), r.chunk_ids) for r in data.relations]


def _chunks_for(text: str, evidence: Sequence[tuple[str, str, tuple[str, ...]]]) -> tuple[str, ...]:
    """Chunks behind a model-written finding: those of the relations whose two ends it names."""
    lowered = text.lower()
    found: list[str] = []
    for source, target, chunk_ids in evidence:
        if source in lowered and target in lowered:
            found.extend(c for c in chunk_ids if c not in found)
    return tuple(found[:6])


def build_reporter(client: ChatClient | None, max_tokens: int) -> Reporter:
    return LlmReporter(client, max_tokens) if client is not None else LocalReporter()
