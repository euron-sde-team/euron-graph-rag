"""Duplicate entity resolution: which names in a project mean the same thing.

Four rules, all deterministic and all explainable in the UI:

1. **alias**: one entity already lists the other's name as an alias.
2. **fuzzy**: near-identical spellings of the same type ("Northgate Sensors", "Northgate Sensers").
3. **containment**: a shorter name is the start or the end of exactly one longer name of a
   compatible type ("Okafor" in "Mira Okafor", "Helios" in "Helios Robotics"). Two candidates
   make it ambiguous and nothing is merged.
4. **acronym**: a short all-letter name equals the initials of exactly one longer name.

Merging is transitive (union-find). The survivor is the most mentioned, then the longest name.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from graphrag.graph.names import acronym, entity_key, name_tokens

FUZZY_RATIO = 0.9
MAX_FUZZY_COMPARISONS = 250_000
_COMPATIBLE_PAIRS = frozenset(
    {frozenset({"CONCEPT", "TECHNOLOGY"}), frozenset({"PRODUCT", "TECHNOLOGY"})}
)


@dataclass(frozen=True, slots=True)
class Candidate[K: Hashable]:
    id: K
    name: str
    type: str
    mentions: int = 1
    aliases: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return entity_key(self.name)


@dataclass(slots=True)
class MergeGroup[K: Hashable]:
    survivor: K
    # member id -> the rule that linked it to the group
    members: dict[K, str] = field(default_factory=dict)


def compatible(a: str, b: str) -> bool:
    return a == b or "OTHER" in (a, b) or frozenset({a, b}) in _COMPATIBLE_PAIRS


def merged_type(survivor: str, others: Sequence[str]) -> str:
    """The survivor's type, unless it is vague and a member is specific."""
    if survivor != "OTHER":
        return survivor
    return next((t for t in others if t != "OTHER"), survivor)


class _Groups[K: Hashable]:
    def __init__(self) -> None:
        self.parent: dict[K, K] = {}
        self.reason: dict[K, str] = {}

    def find(self, item: K) -> K:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: K, b: K, reason: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra
            self.reason.setdefault(b, reason)


def find_duplicates[K: Hashable](candidates: Sequence[Candidate[K]]) -> list[MergeGroup[K]]:
    by_id = {c.id: c for c in candidates}
    tokens = {c.id: name_tokens(c.name) for c in candidates}
    groups: _Groups[K] = _Groups()

    # 1. Aliases.
    by_key: dict[str, list[Candidate[K]]] = defaultdict(list)
    for c in candidates:
        by_key[c.key].append(c)
    for c in candidates:
        for alias in c.aliases:
            for other in by_key.get(entity_key(alias), []):
                if other.id != c.id and compatible(c.type, other.type):
                    groups.union(c.id, other.id, "alias")

    # 2. Fuzzy spelling, within a type and a first letter to keep the comparisons few.
    buckets: dict[tuple[str, str], list[Candidate[K]]] = defaultdict(list)
    for c in candidates:
        if len(c.key) >= 6:
            buckets[(c.type, c.key[0])].append(c)
    budget = MAX_FUZZY_COMPARISONS
    for bucket in buckets.values():
        for i, a in enumerate(bucket):
            for b in bucket[i + 1 :]:
                budget -= 1
                if budget < 0:
                    break
                if len(tokens[a.id]) != len(tokens[b.id]) or abs(len(a.key) - len(b.key)) > 2:
                    continue
                if SequenceMatcher(None, a.key, b.key).ratio() >= FUZZY_RATIO:
                    groups.union(a.id, b.id, "fuzzy")

    # 3. Containment and 4. acronym: each short name needs exactly one longer match, counting
    # names already linked as spellings of one as a single match.
    for short in candidates:
        st = tokens[short.id]
        if not st or max(len(t) for t in st) < 3:
            continue
        contained = [
            long
            for long in candidates
            if long.id != short.id
            and len(tokens[long.id]) > len(st)
            and compatible(short.type, long.type)
            and (tokens[long.id][: len(st)] == st or tokens[long.id][-len(st) :] == st)
        ]
        if len({groups.find(long.id) for long in contained}) == 1:
            groups.union(contained[0].id, short.id, "containment")
            continue
        if len(st) == 1 and 2 <= len(st[0]) <= 6 and short.name.replace(".", "").isupper():
            initials = [
                long
                for long in candidates
                if long.id != short.id
                and compatible(short.type, long.type)
                and acronym(long.name) == st[0]
            ]
            if len({groups.find(long.id) for long in initials}) == 1:
                groups.union(initials[0].id, short.id, "acronym")

    clusters: dict[K, list[K]] = defaultdict(list)
    for item in list(groups.parent):
        clusters[groups.find(item)].append(item)
    result: list[MergeGroup[K]] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        survivor = max(members, key=lambda m: (by_id[m].mentions, len(by_id[m].name), str(m)))
        group = MergeGroup[K](survivor)
        for member in members:
            if member != survivor:
                group.members[member] = groups.reason.get(member, "alias")
        result.append(group)
    return sorted(result, key=lambda g: str(g.survivor))
