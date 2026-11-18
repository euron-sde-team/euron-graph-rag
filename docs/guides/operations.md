# Operations

Running GraphRAG day to day: what to watch, how it scales, what to do when something is stuck
and how to back up and upgrade.

## What to watch

| Signal | Where | Meaning |
| --- | --- | --- |
| `GET /livez`, `GET /readyz` | API | Process is up; database, Valkey, storage and queue answer. |
| `GET /metrics` | API and worker (`WORKER_METRICS_PORT`) | Prometheus metrics, below. Keep it off public listeners. |
| `GET /api/v1/system/info` | API | Which providers are active (`extractor`, `reporter`, `answerer`, `embedding`) and the limits in force. |
| Documents page, overview | Web | Each document's pipeline stage, the latest build and any failure with its reason. |

| Metric | Labels | Use |
| --- | --- | --- |
| `graphrag_http_requests_total`, `graphrag_http_request_duration_seconds` | method, route, status | Traffic and latency by route template. |
| `graphrag_documents_parsed_total`, `graphrag_chunks_written_total` | kind, outcome | Ingestion throughput and parse failures. |
| `graphrag_extractions_total`, `graphrag_extraction_duration_seconds` | extractor, outcome | Extraction volume and time; a rise in `failed` or `retry` points at the model provider. |
| `graphrag_entities_written_total`, `graphrag_relations_written_total` | | Graph growth. |
| `graphrag_entities_merged_total` | source (alias, fuzzy, containment, acronym) | Which resolution rules do the work; a spike in `fuzzy` deserves a look. |
| `graphrag_builds_total`, `graphrag_build_duration_seconds` | outcome | Build health and time. |
| `graphrag_queries_total`, `graphrag_query_stage_seconds` | mode, stage | Question volume and where the time goes (embed, passages, seeds, expand, rank, communities, map, reduce, answer). |
| `graphrag_cache_total` | cache (embedding, query), result | Cache hit ratios. |

Logs are JSON with the request id. Events worth alerting on: `build_error`, `extraction_error`,
`extraction_write_error`, `parse_error`, `job_failed`, `reaped_stale_work`, `queue_receive_failed`.

## Scaling

| What | Setting | Notes |
| --- | --- | --- |
| API tasks | `api_min_count`, `api_max_count` (Terraform) | Stateless; scale on CPU. |
| Worker tasks and concurrency | `worker_min_count`, `worker_max_count`, `WORKER_CONCURRENCY` | Parsing, embedding and extraction are CPU bound; a build is one job per project. |
| Database | RDS instance class and storage | Vectors and passages dominate; storage autoscales. Add read capacity before sharding. |
| Vector search | `hnsw.ef_search` is `max(40, 2 x limit)` per query | Raised automatically for wider requests. |
| Query cache | `QUERY_CACHE_TTL_S` | Answers are cached per `graph_version`; a graph change retires them. |

A graph of tens of thousands of entities builds in seconds to a minute with the local
providers. With a model, extraction and reports are the cost: a chunk is one completion and a
community report is one completion, so budget `chunks + communities` calls per full re-run.

## When something is stuck

- **A document stays `processing` or `queued`.** The reaper (one worker holds a Valkey lease)
  re-sends work that has not moved for `STALE_JOB_MINUTES`, only while the queue is empty for
  queued rows, and marks rows failed after three attempts. Reprocess it from the documents
  page.
- **A document `failed`.** The reason is on the row ("This file has no text.", "Extraction
  failed. Try reprocessing the document."). Fix the cause (a provider outage, an unreadable
  file) and choose Process again.
- **A build `failed`.** The previous communities stay in place; the error is on the build.
  Request another from the documents page or `graphrag graph rebuild --project <slug>`.
- **Messages in the dead-letter queue.** Messages hold ids only, so a dead-lettered message is a
  job that failed three times. Fix the cause, then reprocess the document or request a build;
  purge the dead-letter queue afterwards.
- **Answers look stale.** They cannot: the answer cache is keyed by the project's
  `graph_version`. If a model answer looks wrong, open the playground and read the sources.

## Backup and restore

| Data | Protection | Restore |
| --- | --- | --- |
| PostgreSQL (accounts, documents, chunks, the graph, communities, history) | Automated RDS backups (3 days dev, 14 prod), point-in-time recovery | Restore a snapshot or a point in time; run the migrations. |
| Originals and URL snapshots (S3) | Versioning, SSE-KMS | Restore object versions. |
| The graph | Derived data | If the database is restored without it, `POST .../documents/{id}/reprocess` for each document (or a script over the list) rebuilds it from the originals, then a build recreates communities. |

## Upgrades

- Migrations are applied when the API boots (`MIGRATE_ON_BOOT=true`) under an advisory lock,
  so concurrent tasks cannot race; the worker waits for the API to be healthy.
- A change to the embedding width needs documents to be processed again. Old vectors stay and
  are ignored by queries until then.
- A new rule extractor or lexicon applies to documents ingested afterwards; reprocess a
  document to apply it.
- Image and library updates arrive through `apps/api/uv.lock` and `pnpm-lock.yaml`; CI builds
  and scans the images.

## Retention

Documents, the graph and the question history stay until a person deletes them. Deleting a
document removes the entities and relations only it supported. `QUERY_LOG_TEXT=false` stores
questions as empty text. Audit events are kept with the project.
