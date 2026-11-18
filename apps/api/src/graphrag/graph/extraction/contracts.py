"""What an extractor consumes and produces, whichever model is behind it."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChunkInput:
    text: str
    heading: str = ""


@dataclass(frozen=True, slots=True)
class EntityHit:
    name: str
    type: str
    description: str
    # How often the entity appears in the chunk, for ranking its mentions.
    count: int = 1


@dataclass(frozen=True, slots=True)
class RelationHit:
    source: str
    target: str
    predicate: str
    description: str
    weight: float = 1.0
    quote: str = ""


@dataclass(slots=True)
class ChunkExtraction:
    entities: list[EntityHit] = field(default_factory=list)
    relations: list[RelationHit] = field(default_factory=list)


class Extractor(Protocol):
    """Turns the chunks of one document into entities and relations, one result per chunk.

    A relation's `source` and `target` are names that also appear in the same result's
    `entities`. Implementations must be safe to call concurrently.
    """

    name: str

    async def extract(
        self, chunks: Sequence[ChunkInput], entity_types: Sequence[str]
    ) -> list[ChunkExtraction]: ...


def predicate_phrase(predicate: str) -> str:
    """A predicate as a lowercase phrase ("PARTNERED_WITH" -> "partnered with")."""
    return predicate.lower().replace("_", " ")
