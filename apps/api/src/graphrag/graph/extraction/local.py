"""The deterministic extractor: rules over capitalization, word lists and verb patterns.

It needs no model and no network, so tests, demos and screenshots reproduce exactly. It is a
baseline, not a language model: it finds names written with capital letters, types them from
suffixes, titles, first names, places and the verbs around them, and links two entities that
share a sentence through a verb pattern ("acquired", "partnered with", "CEO of"). A
deployment that needs more recall points LLM_PROVIDER at a model instead
(graph/extraction/llm.py); both return the same structures.

Typing is a vote over the whole document, not a decision per sighting: "Helios" is an
organization everywhere once one sentence has said "Helios announced". Single capitalized
words that start a sentence are dropped unless the document also uses them mid-sentence.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from graphrag.core.text import normalize, sentence_spans
from graphrag.graph.extraction import lexicon as lex
from graphrag.graph.extraction.contracts import (
    ChunkExtraction,
    ChunkInput,
    EntityHit,
    RelationHit,
)
from graphrag.graph.names import display_name, entity_key, fold

_PHRASE = re.compile(
    r"(?:(?:Dr|Prof|Mr|Ms|Mrs|Sir)\.?\s+)?[A-Z][\w&'\N{RIGHT SINGLE QUOTATION MARK}\-]*"
    r"(?:\s+(?:(?:of|de|van|von|der|del|da)\s+)?[A-Z][\w&'\N{RIGHT SINGLE QUOTATION MARK}\-]*)*"
)
_CONCEPTS = re.compile(
    r"\b("
    + "|".join(sorted((re.escape(t) for t in lex.CONCEPT_TERMS), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_ROLE_AFTER = re.compile(
    r"^\s*[,(]\s*(?:the\s+|our\s+|a\s+|an\s+|its\s+)?(?:[a-z-]+\s+){0,3}?"
    r"(?:" + "|".join(sorted(lex.ROLE_WORDS)) + r")\b"
)
_WORD = re.compile(r"[a-z][a-z-]*")
MAX_GAP = 100
DESCRIPTION_LIMIT = 240
LIST_JOINS = frozenset({",", "and", ", and", "or", ", or", "&", ", "})

PERSON, ORG, LOC, EVENT = "PERSON", "ORGANIZATION", "LOCATION", "EVENT"
PRODUCT, TECH, CONCEPT, OTHER = "PRODUCT", "TECHNOLOGY", "CONCEPT", "OTHER"


def _passive(verbs: str) -> str:
    """ "was founded in 2015 by": a passive verb, a few words, then "by"."""
    return rf"\b(?:was|were|is|are|been)\s+(?:\w+\s+)?(?:{verbs})\b(?:\s+[\w-]+){{0,4}}?\s+by\b"


def _t(*names: str) -> frozenset[str]:
    return frozenset(names)


ANY: frozenset[str] | None = None
AGENT = _t(PERSON, ORG)
ARTIFACT = _t(PRODUCT, TECH, CONCEPT, ORG)


@dataclass(frozen=True, slots=True)
class Pattern:
    regex: re.Pattern[str]
    predicate: str
    reverse: bool = False
    first: frozenset[str] | None = ANY
    second: frozenset[str] | None = ANY


def _p(
    regex: str,
    predicate: str,
    *,
    reverse: bool = False,
    first: frozenset[str] | None = ANY,
    second: frozenset[str] | None = ANY,
) -> Pattern:
    return Pattern(re.compile(regex), predicate, reverse, first, second)


# Order matters: passive forms and role phrases come before the bare verbs they contain.
# `reverse` means the pattern reads "<second> VERB <first>" (passive voice).
PATTERNS: tuple[Pattern, ...] = (
    _p(
        _passive("co-?founded|founded|established"),
        "FOUNDED",
        reverse=True,
        first=_t(ORG, PRODUCT),
        second=AGENT,
    ),
    _p(
        _passive("acquired|bought|purchased"),
        "ACQUIRED",
        reverse=True,
        first=_t(ORG),
        second=_t(ORG),
    ),
    _p(
        _passive("funded|backed|financed"),
        "INVESTED_IN",
        reverse=True,
        first=_t(ORG, PRODUCT),
        second=AGENT,
    ),
    _p(
        _passive("led|headed|run|directed|chaired"),
        "LEADS",
        reverse=True,
        first=_t(ORG, EVENT),
        second=_t(PERSON),
    ),
    _p(
        r"\b(?:regulated|overseen|licensed|approved|certified) by\b",
        "REGULATES",
        reverse=True,
        second=_t(ORG),
    ),
    _p(
        r"\b(?:hosted|organized|organised|sponsored|convened) by\b",
        "HOSTED",
        reverse=True,
        first=_t(EVENT),
        second=AGENT,
    ),
    _p(r"\b(?:supplied|provided) by\b", "SUPPLIES", reverse=True, first=_t(ORG), second=_t(ORG)),
    _p(
        _passive(
            "developed|built|created|designed|launched|released|made|manufactured|maintained|operated"
        ),
        "DEVELOPED",
        reverse=True,
        first=ARTIFACT,
        second=AGENT,
    ),
    _p(r"\b(?:authored|written|published) by\b", "AUTHORED", reverse=True, second=AGENT),
    _p(
        r"\bpowered by\b|\bbuilt on\b|\bruns on\b|\brelies on\b|\bdepends on\b",
        "USES",
        first=ARTIFACT,
        second=_t(PRODUCT, TECH, CONCEPT),
    ),
    _p(
        r"\b(?:co-?founder|founder)\b.*\b(?:of|at)\b",
        "FOUNDED",
        first=_t(PERSON),
        second=_t(ORG, PRODUCT),
    ),
    _p(
        r"\b(?:ceo|cto|cfo|coo|cio|chair(?:man|woman)?|president|director|head|chief [a-z ]+ officer|general manager)\b.*\b(?:of|at)\b",
        "LEADS",
        first=_t(PERSON),
        second=_t(ORG, EVENT),
    ),
    _p(
        r"\b(?:engineer|scientist|researcher|professor|analyst|lead|manager|architect|vp|vice president|fellow|advisor|adviser|consultant|designer|physician|partner)\b.*\b(?:of|at|for|with)\b",
        "WORKS_AT",
        first=_t(PERSON),
        second=_t(ORG),
    ),
    _p(
        r"\bco-?founded\b|\bfounded\b|\bestablished\b|\bset up\b|\bstarted\b",
        "FOUNDED",
        first=AGENT,
        second=_t(ORG, PRODUCT, EVENT),
    ),
    _p(
        r"\bacquired\b|\bbought\b|\bpurchased\b|\btook over\b|\bacquires\b",
        "ACQUIRED",
        first=_t(ORG),
        second=_t(ORG),
    ),
    _p(r"\bmerged with\b|\bmerges with\b", "MERGED_WITH", first=_t(ORG), second=_t(ORG)),
    _p(
        r"\binvested in\b|\binvests in\b|\bfunded\b|\bbacked\b|\bfinanced\b",
        "INVESTED_IN",
        first=AGENT,
        second=_t(ORG, PRODUCT),
    ),
    _p(
        r"\bpartner(?:ed|s|ing)? with\b|\bcollaborat\w+ with\b|\bteamed up with\b|\bjoint venture with\b|\ballied with\b|\bwork(?:s|ed|ing)? with\b|\btied up with\b",
        "PARTNERED_WITH",
        first=AGENT,
        second=AGENT,
    ),
    _p(
        r"\bsuppl(?:ies|ied|y|ying)\b|\bprovid(?:es|ed|ing)\b.*\bto\b|\bdeliver(?:s|ed)\b.*\bto\b|\bships? .*\bto\b|\bsells? .*\bto\b",
        "SUPPLIES",
        first=_t(ORG),
        second=_t(ORG),
    ),
    _p(
        r"\bcompet(?:es|ed|ing) with\b|\brivals?\b|\bcompetitor of\b",
        "COMPETES_WITH",
        first=_t(ORG, PRODUCT),
        second=_t(ORG, PRODUCT),
    ),
    _p(
        r"\bpart of\b|\bsubsidiary of\b|\bdivision of\b|\bunit of\b|\bbelongs? to\b|\bmember of\b|\bbranch of\b|\bspun (?:out of|off from)\b",
        "PART_OF",
        first=_t(ORG, PRODUCT, TECH),
        second=_t(ORG, PRODUCT, EVENT),
    ),
    _p(
        r"\bregulat\w+\b|\boversees?\b|\boversaw\b|\bapproved\b|\blicen[sc]ed\b",
        "REGULATES",
        first=_t(ORG),
        second=_t(ORG, PRODUCT, TECH),
    ),
    _p(
        r"\bstudied at\b|\bgraduated from\b|\balumn\w+ of\b|\bwas educated at\b",
        "AFFILIATED_WITH",
        first=_t(PERSON),
        second=_t(ORG),
    ),
    _p(
        r"\bworks? (?:at|for)\b|\bworked (?:at|for)\b|\bjoined\b|\bemployed (?:at|by)\b|\bhired by\b",
        "WORKS_AT",
        first=_t(PERSON),
        second=_t(ORG),
    ),
    _p(
        r"\bleads?\b|\bled\b|\bheads?\b|\bruns?\b|\bdirects?\b|\bchairs?\b|\bmanages?\b",
        "LEADS",
        first=_t(PERSON),
        second=_t(ORG, EVENT, PRODUCT),
    ),
    _p(
        r"\bauthored\b|\bwrote\b|\bco-authored\b|\bpublished\b",
        "AUTHORED",
        first=AGENT,
        second=_t(CONCEPT, TECH, PRODUCT, EVENT, OTHER),
    ),
    _p(
        r"\bhosted\b|\borganized\b|\borganised\b|\bconvened\b|\bsponsored\b",
        "HOSTED",
        first=AGENT,
        second=_t(EVENT),
    ),
    _p(
        r"\battended\b|\bspoke at\b|\bpresented at\b|\bkeynote at\b|\bparticipated in\b|\bexhibited at\b|\bwon\b|\bopened\b|\bopens\b|\bwould open\b|\bwill open\b|\bmoderated\b|\bchaired\b|\bpresented\b|\bspoke\b",
        "ATTENDED",
        first=AGENT,
        second=_t(EVENT),
    ),
    _p(
        r"\bdevelop(?:ed|s|ing)\b|\bbuilt\b|\bbuilds\b|\bcreated\b|\bdesigned\b|\blaunched\b|\breleased\b|\bunveiled\b|\bintroduced\b|\bmanufactur\w+\b|\bmakes\b|\bproduces\b",
        "DEVELOPED",
        first=AGENT,
        second=ARTIFACT,
    ),
    _p(
        r"\bintegrat\w+ (?:with|into)\b|\bconnects? to\b|\bconnected to\b",
        "INTEGRATES_WITH",
        first=ARTIFACT,
        second=ARTIFACT,
    ),
    _p(
        r"\buses\b|\bused\b|\badopted\b|\bleverages?\b|\bdeploy\w*\b|\brelies on\b|\bapplies\b|\bemploys\b",
        "USES",
        first=ARTIFACT,
        second=_t(PRODUCT, TECH, CONCEPT),
    ),
    _p(
        r"\b(?:based|headquartered|located|situated|headquarters)\b.*\b(?:in|at|near)\b",
        "LOCATED_IN",
        second=_t(LOC),
    ),
    _p(
        r"\bopened\b.*\b(?:in|at)\b|\boperates\b.*\bin\b|\bexpanded\b.*\b(?:in|into)\b|\bdeployed\b.*\bin\b",
        "LOCATED_IN",
        second=_t(LOC),
    ),
    _p(
        r"^\s*,?\s*(?:in|at|near|outside)\s*$",
        "LOCATED_IN",
        first=_t(ORG, PRODUCT, EVENT),
        second=_t(LOC),
    ),
)


@dataclass(slots=True)
class _Occurrence:
    chunk: int
    sentence: int
    start: int
    end: int
    surface: str
    key: str
    vote: str
    strength: float
    initial: bool


def extract_chunks(chunks: Sequence[ChunkInput], allowed: Sequence[str]) -> list[ChunkExtraction]:
    sentences = [_split(chunk.text) for chunk in chunks]
    occurrences = [
        occ
        for ci, sents in enumerate(sentences)
        for si, sent in enumerate(sents)
        for occ in _scan_sentence(ci, si, sent)
    ]
    mid_seen = {o.key for o in occurrences if not o.initial}
    counts = Counter(o.key for o in occurrences)
    kept = [o for o in occurrences if _keep(o, mid_seen, counts)]

    votes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    surfaces: dict[str, Counter[str]] = defaultdict(Counter)
    for o in kept:
        votes[o.key][o.vote] += o.strength
        surfaces[o.key][display_name(o.surface)] += 1
    types = {key: kind for key, v in votes.items() if (kind := _final_type(v, allowed)) is not None}
    names = {
        key: max(s.items(), key=lambda kv: (kv[1], len(kv[0])))[0] for key, s in surfaces.items()
    }

    by_sentence: dict[tuple[int, int], list[_Occurrence]] = defaultdict(list)
    for o in kept:
        if types.get(o.key) is not None:
            by_sentence[(o.chunk, o.sentence)].append(o)

    inferred: dict[str, str] = {}
    seen: list[dict[str, tuple[int, str]]] = [{} for _ in chunks]
    relations: list[dict[tuple[str, str, str], RelationHit]] = [{} for _ in chunks]
    for ci in range(len(chunks)):
        for si, sent in enumerate(sentences[ci]):
            occs = sorted(by_sentence.get((ci, si), []), key=lambda o: o.start)
            for o in occs:
                count, description = seen[ci].get(o.key, (0, ""))
                seen[ci][o.key] = (count + 1, description or sent[:DESCRIPTION_LIMIT])
            for hit in _relations(sent, occs, names, types, inferred):
                relations[ci].setdefault(
                    (entity_key(hit.source), entity_key(hit.target), hit.predicate), hit
                )
    types.update({key: kind for key, kind in inferred.items() if kind in allowed})

    results = [ChunkExtraction() for _ in chunks]
    for ci, result in enumerate(results):
        for key, (count, description) in seen[ci].items():
            result.entities.append(EntityHit(names[key], str(types[key]), description, count))
        result.relations = list(relations[ci].values())
    return results


class RuleExtractor:
    name = "local"

    async def extract(
        self, chunks: Sequence[ChunkInput], entity_types: Sequence[str]
    ) -> list[ChunkExtraction]:
        return extract_chunks(chunks, entity_types)


# Scanning -------------------------------------------------------------------------------------


def _split(text: str) -> list[str]:
    """Sentences, never crossing a line break: a heading is not the start of the next sentence."""
    sentences: list[str] = []
    for line in normalize(text).split("\n"):
        line = line.strip().lstrip("#").strip()
        sentences.extend(line[s:e].strip() for s, e in sentence_spans(line))
    return [s for s in sentences if s]


def _scan_sentence(chunk: int, index: int, sentence: str) -> list[_Occurrence]:
    found: list[_Occurrence] = []
    concepts = [(m.span(), fold(m.group(1))) for m in _CONCEPTS.finditer(sentence)]
    phrases = list(_PHRASE.finditer(sentence))
    claimed: list[tuple[int, int]] = []
    for (start, end), term in concepts:
        overlapping = [m for m in phrases if m.start() < end and start < m.end()]
        # A concept yields to a longer capitalized name that contains it ("Supply Chain Summit").
        if any(m.start() < start or m.end() > end for m in overlapping):
            continue
        claimed.append((start, end))
        found.append(
            _Occurrence(
                chunk,
                index,
                start,
                end,
                term.capitalize(),
                entity_key(term),
                lex.CONCEPT_TERMS[term],
                3.0,
                False,
            )
        )
    for match in phrases:
        if any(match.start() >= a and match.end() <= b for a, b in claimed):
            continue
        occurrence = _phrase_occurrence(chunk, index, sentence, match)
        if occurrence is not None:
            found.append(occurrence)
    return [o for o in found if o.key]


def _phrase_occurrence(
    chunk: int, index: int, sentence: str, match: re.Match[str]
) -> _Occurrence | None:
    raw = match.group(0)
    tokens = raw.split()
    title = False
    if tokens[0].rstrip(".") in {"Dr", "Prof", "Mr", "Ms", "Mrs", "Sir"}:
        title, tokens = True, tokens[1:]
    while tokens and (tokens[0] in lex.STARTERS or fold(tokens[0]) in lex.ROLE_WORDS):
        tokens = tokens[1:]
    # "CEO of Helios Robotics": the role word was dropped, so the connector goes too.
    while tokens and tokens[0] in {"of", "de", "van", "von", "der", "del", "da"}:
        tokens = tokens[1:]
    if not tokens:
        return None
    tokens[-1] = re.sub(r"['\N{RIGHT SINGLE QUOTATION MARK}]s?$", "", tokens[-1]).rstrip("-")
    name = " ".join(tokens)
    if (
        (len(name) < 2 and not name.isupper())
        or name in lex.NOISE
        or name.isdigit()
        or tokens[0] == "Series"
    ):
        return None
    start = match.start() + raw.index(tokens[0])
    end = start + len(name)
    initial = sentence[:start].strip(" \"'([") == ""
    vote, strength = _classify(tokens, title, sentence[:start], sentence[end:])
    return _Occurrence(chunk, index, start, end, name, entity_key(name), vote, strength, initial)


def _keep(o: _Occurrence, mid_seen: set[str], counts: Counter[str]) -> bool:
    tokens = o.surface.split()
    known = o.strength >= 1.5
    if len(tokens) > 1 or known:
        return True
    # A lone capitalized word with no cue: a sentence opener unless the document also uses
    # it mid-sentence, and a name only if it comes back.
    return not (o.initial and o.key not in mid_seen) and counts[o.key] >= 2


def _classify(tokens: list[str], title: bool, left: str, right: str) -> tuple[str, float]:
    folded = [fold(t) for t in tokens]
    joined = "-".join(folded)
    last, first = folded[-1], folded[0]
    right_words = _WORD.findall(right.lower()[:60])
    right_head = right_words[0] if right_words else ""
    left_words = _WORD.findall(left.lower()[-40:])
    left_tail = left_words[-1] if left_words else ""
    if title:
        return PERSON, 3.0
    if joined in lex.LOCATIONS:
        return LOC, 2.5
    if last in lex.LOCATION_SUFFIXES and len(tokens) > 1:
        return LOC, 2.0
    if last in lex.EVENT_SUFFIXES or (first in lex.EVENT_SUFFIXES and len(tokens) > 1):
        return EVENT, 2.0
    if any(t in lex.ORG_SUFFIXES for t in folded) and len(tokens) > 1:
        return ORG, 2.5
    if (last in lex.PRODUCT_SUFFIXES and len(tokens) > 1) or any(c.isdigit() for c in joined):
        return PRODUCT, 2.0
    if last in lex.TECH_SUFFIXES and len(tokens) > 1:
        return TECH, 2.0
    if len(tokens) == 1 and tokens[0].isupper() and 2 <= len(tokens[0]) <= 6:
        if last in lex.TECH_ACRONYMS:
            return TECH, 2.0
        if last in lex.ORG_ACRONYMS:
            return ORG, 2.0
        return OTHER, 0.5
    if (left_tail in lex.ROLE_WORDS and len(tokens) <= 3) or (
        len(tokens) <= 3 and _ROLE_AFTER.match(right)
    ):
        return PERSON, 2.5
    if first in lex.FIRST_NAMES and 2 <= len(tokens) <= 3:
        return PERSON, 2.2
    if right_head in lex.PERSON_VERBS and 2 <= len(tokens) <= 3 and first not in lex.STARTERS:
        return PERSON, 1.5
    if first in lex.FIRST_NAMES and len(tokens) == 1:
        return PERSON, 1.0 if right_head in lex.PERSON_VERBS else 0.6
    if right_head in lex.ORG_VERBS:
        return ORG, 1.5
    if left_tail == "at" and len(tokens) <= 3:
        return ORG, 0.8
    if left_tail in {"in", "near", "across"} and len(tokens) <= 2:
        return LOC, 0.6
    return OTHER, 0.4


def _final_type(votes: dict[str, float], allowed: Sequence[str]) -> str | None:
    ranked = sorted(((t, w) for t, w in votes.items() if t != OTHER), key=lambda kv: -kv[1])
    chosen = ranked[0][0] if ranked else OTHER
    if chosen in allowed:
        return chosen
    return OTHER if OTHER in allowed else None


# Relations ------------------------------------------------------------------------------------


def _fits(entity_type: str, allowed: frozenset[str] | None) -> bool:
    return allowed is None or entity_type == OTHER or entity_type in allowed


def _relations(
    sentence: str,
    occs: list[_Occurrence],
    names: dict[str, str],
    types: dict[str, str],
    inferred: dict[str, str],
) -> list[RelationHit]:
    ordered = [
        o
        for i, o in enumerate(occs)
        if not any(p.key == o.key and p.start == o.start for p in occs[:i])
    ]
    hits: list[RelationHit] = []
    for i, a in enumerate(ordered):
        for j in range(i + 1, min(i + 4, len(ordered))):
            b = ordered[j]
            if a.key == b.key:
                continue
            if j > i + 1 and not _is_list(sentence, ordered, i, j, types):
                continue
            between = sentence[a.end : b.start]
            if len(between) > MAX_GAP or ";" in between:
                continue
            hit = _shared_subject(sentence, ordered, i, b, between, names, types, inferred)
            if hit is None:
                hit = _match(sentence, a, b, between, names, types, inferred)
            if hit is None and j == i + 1 and len(ordered) <= 5:
                hit = _fallback(sentence, a, b, between, names)
            if hit is not None:
                hits.append(hit)
    return hits


def _shared_subject(
    sentence: str,
    ordered: list[_Occurrence],
    i: int,
    b: _Occurrence,
    between: str,
    names: dict[str, str],
    types: dict[str, str],
    inferred: dict[str, str],
) -> RelationHit | None:
    """ "A acquired B in 2024 and partnered with C": the verb after "and" belongs to A."""
    clauses = re.split(r"\band\b|,|\bwhile\b|\bthen\b", between.lower())
    if len(clauses) < 2 or i == 0:
        return None
    subject = ordered[0]
    if subject.key == b.key or types[subject.key] not in AGENT:
        return None
    return _match(sentence, subject, b, clauses[-1], names, types, inferred)


def _is_list(
    sentence: str, ordered: list[_Occurrence], i: int, j: int, types: dict[str, str]
) -> bool:
    """`a ... b` may skip entities only when they form a list with b ("X acquired Y and Z")."""
    for k in range(i + 1, j):
        gap = sentence[ordered[k].end : ordered[k + 1].start].strip().lower()
        if gap not in LIST_JOINS or types.get(ordered[k].key) != types.get(ordered[k + 1].key):
            return False
    return True


def _match(
    sentence: str,
    a: _Occurrence,
    b: _Occurrence,
    between: str,
    names: dict[str, str],
    types: dict[str, str],
    inferred: dict[str, str],
) -> RelationHit | None:
    text = between.lower()
    ta, tb = types[a.key], types[b.key]
    for pattern in PATTERNS:
        if not pattern.regex.search(text):
            continue
        # Type constraints are written in the order the names appear in the sentence. An
        # entity still typed OTHER satisfies any constraint, and a constraint naming one
        # type teaches the entity that type (see `inferred` in extract_chunks).
        if not _fits(ta, pattern.first) or not _fits(tb, pattern.second):
            continue
        if ta == OTHER and pattern.first and len(pattern.first) == 1:
            inferred[a.key] = next(iter(pattern.first))
        if tb == OTHER and pattern.second and len(pattern.second) == 1:
            inferred[b.key] = next(iter(pattern.second))
        source, target = (b, a) if pattern.reverse else (a, b)
        quote = sentence[: DESCRIPTION_LIMIT * 2]
        return RelationHit(
            names[source.key], names[target.key], pattern.predicate, quote, 1.0, quote
        )
    return None


def _fallback(
    sentence: str, a: _Occurrence, b: _Occurrence, between: str, names: dict[str, str]
) -> RelationHit | None:
    stripped = between.strip().lower()
    bare = {"", "and", "or", "&", "in", "at", "of", "for", "to", "with", "on", "by", "from"}
    # A verb with no known pattern means the sentence says something specific that a generic
    # edge would misstate, so no edge is better than a vague one.
    if any(
        w in lex.ORG_VERBS | lex.PERSON_VERBS or w.endswith(("ed", "ing"))
        for w in _WORD.findall(stripped)
    ):
        return None
    if (
        not stripped
        or stripped.startswith(",")
        or stripped.strip(" ,") in bare
        or len(between) > 40
    ):
        return None
    return RelationHit(
        names[a.key],
        names[b.key],
        "RELATED_TO",
        sentence[: DESCRIPTION_LIMIT * 2],
        0.4,
        sentence[: DESCRIPTION_LIMIT * 2],
    )
