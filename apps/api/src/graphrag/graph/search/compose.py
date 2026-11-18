"""Answers: an extractive composer that runs offline, and a model composer.

The extractive composer answers with the sentences of the context that best match the
question, each followed by the citation of the source it came from. It cannot paraphrase or
infer, which is exactly what makes it a trustworthy offline default: whatever it says is
quoted from a source. The model composer is told to cite the same way and is checked.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from graphrag.ai.llm import ChatClient
from graphrag.core.text import content_terms, split_sentences
from graphrag.graph.extraction.llm import parse_reply
from graphrag.graph.search.contracts import Answer, ContextItem, Point

NO_ANSWER = "The knowledge graph has no passages that answer this question."
MIN_SENTENCE_CHARS = 25
MAX_SENTENCE_CHARS = 360
MIN_RELEVANCE = 0.18
_CITATION = re.compile(r"\[(\d{1,3})\]")

ANSWER_SYSTEM = (
    "You answer questions from numbered sources taken from a knowledge graph built over the "
    "user's documents. Use only the sources. Cite the source of every claim as [n] right after "
    "it. If the sources do not contain the answer, say so plainly. Be concise and direct."
)
MAP_SYSTEM = (
    "You read one community report from a knowledge graph and list the points that help answer "
    'a question. Reply with one JSON object and nothing else: {"points": [{"description": str, '
    '"score": int}]} where score from 0 to 100 says how much the point helps answer the '
    "question. Return an empty list when the report is irrelevant."
)


def _sentences(item: ContextItem) -> list[str]:
    return [
        s
        for s in split_sentences(item.text.replace("\n", " "))
        if MIN_SENTENCE_CHARS <= len(s) <= MAX_SENTENCE_CHARS
    ]


def score_sentences(
    question: str, items: Sequence[ContextItem]
) -> list[tuple[float, int, str, ContextItem]]:
    """Every sentence of the context with its relevance to the question, best first."""
    query_terms = set(content_terms(question))
    pool = [(item, s, set(content_terms(s))) for item in items for s in _sentences(item)]
    if not query_terms or not pool:
        return []
    document_frequency: Counter[str] = Counter()
    for _, _, terms in pool:
        document_frequency.update(terms & query_terms)
    idf = {t: math.log(1 + len(pool) / (1 + document_frequency[t])) for t in query_terms}
    present = sum(idf[t] for t in query_terms if document_frequency[t])
    if present == 0:
        return []
    top = max((item.score for item in items), default=1.0) or 1.0
    scored = []
    for position, (item, sentence, terms) in enumerate(pool):
        overlap = sum(idf[t] for t in terms & query_terms) / present
        # A little of the retrieval score breaks ties between equally matching sentences.
        weighted = overlap * (0.8 + 0.2 * (item.score / top))
        scored.append((weighted, position, sentence, item))
    return sorted(scored, key=lambda row: (-row[0], row[1]))


def extractive_answer(question: str, items: Sequence[ContextItem], *, sentences: int = 4) -> Answer:
    chosen: list[tuple[float, int, str, ContextItem]] = []
    for row in score_sentences(question, items):
        if row[0] < MIN_RELEVANCE and chosen:
            break
        if row[0] < MIN_RELEVANCE:
            continue
        words = set(content_terms(row[2]))
        if any(len(words & set(content_terms(c[2]))) / max(1, len(words)) > 0.8 for c in chosen):
            continue
        chosen.append(row)
        if len(chosen) == sentences:
            break
    if not chosen:
        return Answer(NO_ANSWER, "local")
    # Read in source order: the best sentence first would scramble a narrative.
    chosen.sort(key=lambda row: row[1])
    text = " ".join(f"{sentence.rstrip('.!? ')} [{item.n}]." for _, _, sentence, item in chosen)
    return Answer(text, "local", cited=sorted({item.n for _, _, _, item in chosen}))


def local_points(question: str, item: ContextItem, *, limit: int = 3) -> list[Point]:
    """The deterministic map step: a community's sentences scored against the question."""
    rows = score_sentences(question, [item])
    return [
        Point(sentence, round(score * 100, 1))
        for score, _, sentence, _ in rows[:limit]
        if score >= MIN_RELEVANCE
    ]


def _numbered(items: Sequence[ContextItem]) -> str:
    return "\n\n".join(f"[{item.n}] {item.label}\n{item.text}" for item in items)


async def model_answer(
    client: ChatClient, question: str, items: Sequence[ContextItem], max_tokens: int
) -> Answer:
    user = f"Sources:\n\n{_numbered(items)}\n\nQuestion: {question}"
    text, usage = await client.complete(
        [{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )
    valid = {item.n for item in items}
    cited = sorted({int(m) for m in _CITATION.findall(text) if int(m) in valid})
    # A marker that names no source would point the reader at nothing: drop it.
    cleaned = _CITATION.sub(lambda m: m.group(0) if int(m.group(1)) in valid else "", text)
    return Answer(
        cleaned.strip(),
        f"{client.provider}:{client.default_model}",
        usage.prompt_tokens,
        usage.completion_tokens,
        cited,
    )


async def model_points(
    client: ChatClient, question: str, item: ContextItem, max_tokens: int
) -> tuple[list[Point], int, int]:
    user = f"Question: {question}\n\nReport: {item.label}\n{item.text}"
    text, usage = await client.complete(
        [{"role": "system", "content": MAP_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )
    payload = parse_reply(text) or {}
    points: list[Point] = []
    for raw in payload.get("points") or []:
        if isinstance(raw, dict) and raw.get("description"):
            try:
                score = float(raw.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            points.append(Point(str(raw["description"])[:400], max(0.0, min(100.0, score))))
    return points, usage.prompt_tokens, usage.completion_tokens
