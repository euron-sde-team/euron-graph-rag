# 0001: PostgreSQL and pgvector are the graph store

Status: accepted

## Context

The graph needs nodes, edges, provenance (which passage says so), vectors for entities,
passages and community reports, full-text search, transactions and a way to filter every read
by project. Candidates: a graph database next to a vector store, or one relational database.

## Decision

Store everything in PostgreSQL 16: entities, relations, mentions and evidence as ordinary
tables, vectors in `vector` columns with partial HNSW indexes per embedding width, passages with
a generated `tsvector`, names with a trigram index.

## Consequences

- One system to run, back up and secure; RDS is a managed answer on AWS.
- Provenance, merges and rebuilds are transactions: a build replaces every community
  atomically, a merge moves mentions and relations together.
- Neighbourhood walks are indexed joins, a few per hop, which is fast at the sizes of one
  project (tens of thousands of entities). A graph database would win on deep traversals over
  millions of edges; that is not this product's workload.
- Vector widths share one schema (untyped column plus `embedding_dim`) so a deployment can
  change models without a migration; each width needs its own partial index.
