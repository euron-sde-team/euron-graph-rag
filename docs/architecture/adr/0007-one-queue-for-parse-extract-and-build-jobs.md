# 0007: One queue for parse, extract and build jobs

Status: accepted

## Context

Three kinds of background work exist: parsing and embedding a document, extracting its graph
facts and building communities. Separate queues triple the infrastructure; a single queue needs
care so a slow build does not starve ingestion.

## Decision

One SQS queue with a dead-letter queue. Messages carry only ids and a kind; handlers re-read
rows and are idempotent. Documents carry a `stage`, builds a `status`, so the UI shows
progress without reading the queue. Builds coalesce: at most one queued build per project, and a
build waits for the project's documents to finish before it reads the graph. A reaper under a
Valkey lease re-sends stuck work.

## Consequences

- The worker needs no routing; concurrency is one setting.
- A duplicate, lost or late message is harmless.
- During a large upload, builds run once at the end instead of once per document.
- If extraction and builds need different scaling, the same code runs with two queues by
  splitting `Job` kinds across workers; nothing else changes.
