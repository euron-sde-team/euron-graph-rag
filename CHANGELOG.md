# Changelog

All notable changes to Euron GraphRAG are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

First release.

### Added

- Ingestion pipeline: PDF, Word, Markdown, HTML, text and CSV files, pasted text and web pages are
  parsed, cleaned, chunked and embedded; each document shows its stage.
- Entity and relation extraction behind one interface: a deterministic rule extractor for
  offline use, and OpenAI-compatible and Ollama model extractors with lenient reply parsing.
- Entity resolution across documents (alias, fuzzy spelling, containment, acronym) with a
  preview, manual merge, rename, retype and delete.
- Hierarchical community detection (Louvain with a connectivity guarantee) and generated
  community reports with findings that cite their passages.
- Local, global and hybrid search with citations, the subgraph used, community reports used and
  a per-step trace; query history and an answer cache keyed by graph version.
- Web app: overview dashboard, documents and pipeline view, interactive graph explorer,
  entities, communities hierarchy, query playground, project settings, members, API keys and
  activity.
- Projects with owner, editor and viewer roles, project-bound API keys, audit trail, rate limits.
- PostgreSQL with pgvector (HNSW per embedding width), Valkey, SQS worker with dead-letter queue
  and reaper, S3 originals with KMS.
- Docker Compose stack on the Floci AWS emulator provisioned by the production Terraform;
  Terraform modules and environments for AWS (dev and prod).
- Demo data (`make demo`), Playwright end-to-end suite, QA crawl with axe, screenshot and tour
  capture, unit and integration test suites, documentation and ADRs.
