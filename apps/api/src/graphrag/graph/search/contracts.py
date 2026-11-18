"""What retrieval hands to an answerer: numbered, citable context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class ContextItem:
    """One numbered source. The number is what an answer cites as [n]."""

    n: int
    kind: Literal["chunk", "community"]
    id: str
    label: str
    text: str
    score: float
    document_id: str | None = None
    document_title: str | None = None
    location: str | None = None
    # A community's supporting chunks: where its claims come from.
    chunk_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class Answer:
    text: str
    answerer: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # The numbers of the context items the answer actually cites.
    cited: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Point:
    """One claim a map step found in one community, with how well it answers the question."""

    text: str
    score: float
