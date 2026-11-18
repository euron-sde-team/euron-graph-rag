# 0005: Conservative, explainable entity resolution rules

Status: accepted

## Context

Without resolution the graph fills with "Helios", "Helios Robotics" and "Helios Robotics Inc".
Aggressive merging is worse: wrongly merging two people corrupts every answer that touches
them.

## Decision

Resolve with four deterministic rules, each reported as the reason for a merge: a known alias,
a near-identical spelling of the same type, a name that starts or ends another name (only when
exactly one candidate matches) and an acronym equal to the initials of exactly one name. Types
must be compatible (the same, or one is OTHER). Names are normalized first (case, accents,
titles, possessives, corporate suffixes). A survivor keeps merged names as aliases and the most
specific type. No embedding similarity is used.

## Consequences

- An ambiguous short name ("Meridian", with a company and a product that start with it) is left
  alone; a person can merge it by hand from the duplicates tab.
- Every automatic merge is explainable and shown before it happens (`/graph/duplicates`).
- The alias index means a name merged once is recognised on later ingestion.
- Recall is lower than an embedding-based resolver; precision is what a graph that people
  cite needs.
