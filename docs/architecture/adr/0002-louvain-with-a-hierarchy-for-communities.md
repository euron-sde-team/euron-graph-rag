# 0002: Louvain with a connectivity guarantee and a hierarchy for communities

Status: accepted

## Context

Global search and the explorer need communities at several levels. GraphRAG uses hierarchical
Leiden; the maintained Python implementations pull in native dependencies (igraph, graspologic
with numpy and scipy pins) that are heavy for an image that otherwise needs none of them.

## Decision

Implement Louvain in pure Python (`graph/communities.py`) with a seeded visiting order and
sorted ties, so results are deterministic. Add what Leiden's refinement is for: split every
community into connected components. Build the hierarchy by partitioning each community larger
than six entities again on its own subgraph (slightly higher resolution), down to the project's
level count, absorbing singletons into their strongest neighbour.

## Consequences

- No native dependencies; the algorithm is a few hundred lines with unit tests (planted groups
  are recovered, levels nest, every community is connected).
- Louvain can leave a community internally weak where Leiden would not; the connectivity split
  removes the worst case (disconnected communities) and the resolution is a project setting.
- Level 0 is the coarsest; a branch that cannot split stands for itself at deeper levels.
- If graphs grow far past what Python handles in seconds, the function can be swapped for a
  native Leiden behind the same signature.
