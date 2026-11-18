"""The model extractor: one chat completion per chunk, JSON in and out.

The prompt asks for entities and relations as one JSON object. Models wrap JSON in prose or
code fences, truncate it and invent types, so the reply is parsed leniently and every field
is normalized; a chunk whose reply cannot be parsed at all falls back to the rule extractor,
so one bad completion never leaves a hole in the graph.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from typing import Any

from graphrag.ai.llm import ChatClient
from graphrag.core.logging import get_logger
from graphrag.graph.extraction.contracts import (
    ChunkExtraction,
    ChunkInput,
    EntityHit,
    RelationHit,
)
from graphrag.graph.extraction.local import extract_chunks
from graphrag.graph.names import display_name, entity_key

log = get_logger("graphrag.extraction")
CONCURRENCY = 4
MAX_TEXT_CHARS = 6000

SYSTEM = (
    "You extract a knowledge graph from a passage. Reply with one JSON object and nothing "
    'else: {"entities": [{"name": str, "type": str, "description": str}], '
    '"relations": [{"source": str, "target": str, "predicate": str, "description": str}]}. '
    "Use only the entity types listed by the user. Names are written as in the passage, "
    "without titles. A description is one sentence taken from or paraphrasing the passage. "
    "A predicate is a short UPPER_SNAKE_CASE verb phrase such as FOUNDED, ACQUIRED, WORKS_AT, "
    "LOCATED_IN, PARTNERED_WITH, USES. Both ends of every relation must appear in entities. "
    "Do not invent facts that the passage does not state."
)


def build_messages(chunk: ChunkInput, entity_types: Sequence[str]) -> list[dict[str, str]]:
    heading = f"Section: {chunk.heading}\n" if chunk.heading else ""
    types = ", ".join(entity_types)
    user = f"Entity types: {types}\n\n{heading}Passage:\n{chunk.text[:MAX_TEXT_CHARS]}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_PREDICATE = re.compile(r"[^A-Z0-9]+")


def parse_reply(text: str) -> dict[str, Any] | None:
    """The first JSON object in a model reply, or None."""
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for candidate in candidates:
        start = candidate.find("{")
        while start != -1:
            depth, in_string, escaped = 0, False, False
            for end in range(start, len(candidate)):
                ch = candidate[end]
                if in_string:
                    escaped = (ch == "\\") and not escaped
                    if ch == '"' and not escaped:
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            value = json.loads(candidate[start : end + 1])
                        except json.JSONDecodeError:
                            break
                        if isinstance(value, dict):
                            return value
                        break
            start = candidate.find("{", start + 1)
    return None


def normalize_predicate(value: object) -> str:
    text = _PREDICATE.sub("_", str(value).upper()).strip("_")
    return text[:48] or "RELATED_TO"


def to_extraction(payload: dict[str, Any], allowed: Sequence[str]) -> ChunkExtraction:
    result = ChunkExtraction()
    by_key: dict[str, EntityHit] = {}

    def add(name: object, kind: object, description: object) -> str | None:
        if not isinstance(name, str) or not (shown := display_name(name)) or not entity_key(shown):
            return None
        kind_name = str(kind or "OTHER").strip().upper().replace(" ", "_")
        if kind_name not in allowed:
            kind_name = "OTHER" if "OTHER" in allowed else str(allowed[0])
        key = entity_key(shown)
        if key not in by_key:
            by_key[key] = EntityHit(shown, kind_name, str(description or "").strip()[:240])
        return key

    for item in payload.get("entities") or []:
        if isinstance(item, dict):
            add(item.get("name"), item.get("type"), item.get("description"))
    seen: set[tuple[str, str, str]] = set()
    for item in payload.get("relations") or []:
        if not isinstance(item, dict):
            continue
        source = add(item.get("source"), "OTHER", "")
        target = add(item.get("target"), "OTHER", "")
        if source is None or target is None or source == target:
            continue
        predicate = normalize_predicate(item.get("predicate") or "RELATED_TO")
        if (source, target, predicate) in seen:
            continue
        seen.add((source, target, predicate))
        description = str(item.get("description") or "").strip()[:480]
        result.relations.append(
            RelationHit(
                by_key[source].name, by_key[target].name, predicate, description, 1.0, description
            )
        )
    result.entities = list(by_key.values())
    return result


class LlmExtractor:
    def __init__(self, client: ChatClient, max_tokens: int) -> None:
        self.client = client
        self.name = f"{client.provider}:{client.default_model}"
        self._max_tokens = max_tokens

    async def extract(
        self, chunks: Sequence[ChunkInput], entity_types: Sequence[str]
    ) -> list[ChunkExtraction]:
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(chunk: ChunkInput) -> ChunkExtraction:
            async with gate:
                text, _ = await self.client.complete(
                    build_messages(chunk, entity_types), max_tokens=self._max_tokens
                )
            payload = parse_reply(text)
            if payload is None:
                log.warning("extraction_reply_unparsable", chars=len(text))
                return extract_chunks([chunk], entity_types)[0]
            return to_extraction(payload, entity_types)

        return list(await asyncio.gather(*(one(c) for c in chunks)))
