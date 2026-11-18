import random

from graphrag.graph.communities import (
    build_hierarchy,
    communities_at,
    connected_components,
    louvain,
    modularity,
)


def planted(groups: int = 4, size: int = 15, density: float = 0.4, seed: int = 1):
    rng = random.Random(seed)
    nodes = [f"n{i:03d}" for i in range(groups * size)]
    edges = []
    for g in range(groups):
        members = nodes[g * size : (g + 1) * size]
        for i, a in enumerate(members):
            edges.extend((a, b, 1.0) for b in members[i + 1 :] if rng.random() < density)
        edges.append((members[0], members[1], 1.0))
    edges.append((nodes[3], nodes[size + 4], 1.0))
    if groups > 2:
        edges.append((nodes[size + 7], nodes[2 * size + 1], 1.0))
    return nodes, edges


def test_louvain_recovers_planted_groups() -> None:
    nodes, edges = planted()
    parts = louvain(nodes, edges)
    assert [len(p) for p in parts] == [15, 15, 15, 15]
    for part in parts:
        assert len({n[1:4] and int(n[1:]) // 15 for n in part}) == 1
    assert modularity(parts, edges) > 0.6


def test_louvain_is_deterministic() -> None:
    nodes, edges = planted()
    assert louvain(nodes, edges, seed=7) == louvain(nodes, edges, seed=7)


def test_a_graph_without_edges_has_no_communities() -> None:
    assert build_hierarchy(["a", "b", "c"], []) == []
    assert louvain(["a", "b"], []) == [frozenset({"a"}), frozenset({"b"})]


def test_hierarchy_nests_and_every_community_is_connected() -> None:
    nodes, edges = planted(groups=3, size=24)
    levels = build_hierarchy(nodes, edges, max_levels=3, split_above=6)
    assert len(levels) >= 2
    by_ref = {n.ref: n for level in levels for n in level}
    for level in levels:
        for node in level:
            assert len(node.members) >= 2
            inside = [(u, v, w) for u, v, w in edges if u in node.members and v in node.members]
            assert len(connected_components(sorted(node.members), inside)) == 1
            if node.parent is not None:
                assert node.members <= by_ref[node.parent].members
    for level in levels[1:]:
        for parent_ref in {n.parent for n in level}:
            children = [n for n in level if n.parent == parent_ref]
            covered = set().union(*(c.members for c in children))
            assert covered == by_ref[parent_ref].members


def test_small_communities_do_not_split() -> None:
    edges = [("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0)]
    levels = build_hierarchy(["a", "b", "c", "x"], edges, split_above=6)
    assert [[sorted(n.members) for n in level] for level in levels] == [[["a", "b", "c"]]]


def test_communities_at_a_level_include_branches_that_stopped_splitting() -> None:
    nodes, edges = planted(groups=2, size=30)
    edges += [("z1", "z2", 1.0), ("z2", "z3", 1.0), ("z1", "z3", 1.0)]
    levels = build_hierarchy([*nodes, "z1", "z2", "z3"], edges, max_levels=3, split_above=6)
    covered = set().union(*(n.members for n in communities_at(levels, 2)))
    assert {"z1", "z2", "z3"} <= covered
    assert covered == set().union(*(n.members for n in levels[0]))


def test_connected_components_are_largest_first() -> None:
    parts = connected_components(["a", "b", "c", "d", "e"], [("a", "b", 1), ("b", "c", 1)])
    assert [len(p) for p in parts] == [3, 1, 1]
