"""Community detection: Louvain modularity optimization with a hierarchy on top.

Louvain moves nodes between communities while modularity grows, collapses each community
into one node and repeats. It is deterministic here (seeded visiting order, sorted ties).
Two additions make it behave like the hierarchical Leiden used by GraphRAG:

- **Connectivity guarantee.** A community that is not connected is split into its connected
  components, the defect Leiden's refinement phase exists to remove.
- **Hierarchy.** Level 0 is the Louvain partition of the whole graph. Each community larger
  than `split_above` is partitioned again on its own subgraph, which gives the next level,
  down to `max_levels`. A community that does not split stays at its level and has no
  children. Every child is a subset of its parent, so levels nest.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

Edge = tuple[str, str, float]


def _adjacency(nodes: Sequence[str], edges: Sequence[Edge]) -> dict[str, dict[str, float]]:
    adjacency: dict[str, dict[str, float]] = {n: {} for n in nodes}
    for u, v, w in edges:
        if u == v or u not in adjacency or v not in adjacency or w <= 0:
            continue
        adjacency[u][v] = adjacency[u].get(v, 0.0) + w
        adjacency[v][u] = adjacency[v].get(u, 0.0) + w
    return adjacency


def louvain(
    nodes: Sequence[str],
    edges: Sequence[Edge],
    *,
    resolution: float = 1.0,
    seed: int = 42,
) -> list[frozenset[str]]:
    """Partition `nodes` into communities, largest first. Edges are undirected and weighted."""
    ordered = sorted(nodes)
    adjacency = _adjacency(ordered, edges)
    rng = random.Random(seed)
    # Each current node stands for the original nodes it has absorbed.
    members: dict[str, set[str]] = {n: {n} for n in ordered}
    graph = adjacency
    while True:
        assignment = _local_moves(graph, resolution, rng)
        groups: dict[str, list[str]] = defaultdict(list)
        for node, community in assignment.items():
            groups[community].append(node)
        if len(groups) == len(graph):
            break
        merged_members: dict[str, set[str]] = {}
        merged_graph: dict[str, dict[str, float]] = {}
        names = {c: min(nodes_) for c, nodes_ in groups.items()}
        for community, nodes_ in groups.items():
            name = names[community]
            merged_members[name] = set().union(*(members[n] for n in nodes_))
            merged_graph.setdefault(name, {})
        for u, neighbours in graph.items():
            cu = names[assignment[u]]
            for v, w in neighbours.items():
                cv = names[assignment[v]]
                # Internal weight stays on the merged node as a self-loop: it still counts
                # towards the node's degree, which the gain formula needs.
                merged_graph[cu][cv] = merged_graph[cu].get(cv, 0.0) + w
        members, graph = merged_members, merged_graph
    partition = [frozenset(m) for m in members.values()]
    return sorted(partition, key=lambda c: (-len(c), min(c)))


def _local_moves(
    graph: dict[str, dict[str, float]], resolution: float, rng: random.Random
) -> dict[str, str]:
    degree = {n: sum(neighbours.values()) for n, neighbours in graph.items()}
    two_m = sum(degree.values())
    community = {n: n for n in graph}
    if two_m == 0:
        return community
    total = dict(degree)
    order = sorted(graph)
    for _ in range(50):
        rng.shuffle(order)
        moved = False
        for node in order:
            current = community[node]
            links: dict[str, float] = defaultdict(float)
            for neighbour, weight in graph[node].items():
                if neighbour != node:
                    links[community[neighbour]] += weight
            total[current] -= degree[node]
            best, best_gain = (
                current,
                links.get(current, 0.0) - resolution * total[current] * degree[node] / two_m,
            )
            for candidate in sorted(links):
                gain = links[candidate] - resolution * total[candidate] * degree[node] / two_m
                if gain > best_gain + 1e-12:
                    best, best_gain = candidate, gain
            total[best] += degree[node]
            if best != current:
                community[node] = best
                moved = True
        if not moved:
            break
    return community


def connected_components(nodes: Sequence[str], edges: Sequence[Edge]) -> list[frozenset[str]]:
    adjacency = _adjacency(nodes, edges)
    seen: set[str] = set()
    components: list[frozenset[str]] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack, component = [start], set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            component.add(node)
            stack.extend(n for n in adjacency[node] if n not in seen)
        components.append(frozenset(component))
    return sorted(components, key=lambda c: (-len(c), min(c)))


def modularity(
    partition: Sequence[frozenset[str]], edges: Sequence[Edge], resolution: float = 1.0
) -> float:
    nodes = [n for part in partition for n in part]
    adjacency = _adjacency(nodes, edges)
    degree = {n: sum(a.values()) for n, a in adjacency.items()}
    two_m = sum(degree.values())
    if two_m == 0:
        return 0.0
    score = 0.0
    for part in partition:
        inside = sum(w for u in part for v, w in adjacency[u].items() if v in part)
        total = sum(degree[u] for u in part)
        score += inside / two_m - resolution * (total / two_m) ** 2
    return score


@dataclass(slots=True)
class CommunityNode:
    level: int
    ordinal: int
    members: frozenset[str]
    parent: tuple[int, int] | None = None
    children: list[tuple[int, int]] = field(default_factory=list)

    @property
    def ref(self) -> tuple[int, int]:
        return (self.level, self.ordinal)


def _connected_parts(part: frozenset[str], edges: Sequence[Edge]) -> list[frozenset[str]]:
    inside = [(u, v, w) for u, v, w in edges if u in part and v in part]
    return connected_components(sorted(part), inside)


def _absorb_singletons(parts: list[frozenset[str]], edges: Sequence[Edge]) -> list[frozenset[str]]:
    """Fold one-node parts into the part they share the most weight with."""
    groups = [set(p) for p in parts if len(p) > 1]
    if not groups:
        return []
    owner = {n: i for i, g in enumerate(groups) for n in g}
    for single in (next(iter(p)) for p in parts if len(p) == 1):
        weight: dict[int, float] = defaultdict(float)
        for u, v, w in edges:
            other = v if u == single else u if v == single else None
            if other in owner:
                weight[owner[other]] += w
        if weight:
            best = max(sorted(weight), key=lambda i: weight[i])
            groups[best].add(single)
            owner[single] = best
    return [frozenset(g) for g in groups]


def build_hierarchy(
    nodes: Sequence[str],
    edges: Sequence[Edge],
    *,
    max_levels: int = 3,
    min_size: int = 2,
    split_above: int = 6,
    resolution: float = 1.0,
    seed: int = 42,
) -> list[list[CommunityNode]]:
    """Levels of communities, coarsest first. Isolated nodes belong to no community."""
    connected = [n for n, nb in _adjacency(nodes, edges).items() if nb]
    if not connected:
        return []
    top: list[frozenset[str]] = []
    for part in louvain(connected, edges, resolution=resolution, seed=seed):
        top.extend(_connected_parts(part, edges))
    top = sorted((p for p in top if len(p) >= min_size), key=lambda c: (-len(c), min(c)))
    levels: list[list[CommunityNode]] = [[CommunityNode(0, i, p) for i, p in enumerate(top)]]
    for level in range(1, max_levels):
        next_nodes: list[CommunityNode] = []
        created: list[tuple[CommunityNode, list[frozenset[str]]]] = []
        for parent in levels[-1]:
            if len(parent.members) <= split_above:
                continue
            inside = [(u, v, w) for u, v, w in edges if u in parent.members and v in parent.members]
            pieces = louvain(
                sorted(parent.members), inside, resolution=resolution * 1.2, seed=seed + level
            )
            refined: list[frozenset[str]] = []
            for piece in pieces:
                refined.extend(_connected_parts(piece, inside))
            refined = _absorb_singletons(refined, inside)
            if len(refined) < 2:
                continue
            created.append((parent, sorted(refined, key=lambda c: (-len(c), min(c)))))
        if not created:
            break
        for parent, pieces in created:
            for piece in pieces:
                node = CommunityNode(level, len(next_nodes), piece, parent=parent.ref)
                parent.children.append(node.ref)
                next_nodes.append(node)
        levels.append(next_nodes)
    return levels


def communities_at(levels: Sequence[Sequence[CommunityNode]], level: int) -> list[CommunityNode]:
    """The communities that describe the graph at `level`: those of that level, plus
    shallower ones that never split."""
    chosen: list[CommunityNode] = []
    for depth, nodes in enumerate(levels):
        if depth > level:
            break
        chosen.extend(n for n in nodes if depth == level or not n.children)
    return chosen
