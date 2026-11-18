# Configuration

Every setting is an environment variable read once at start by `core/config.py` and validated
(a bad value stops the process with the reason). Names below are the container variables; the
Compose files map `GRAPHRAG_*` variables from `deploy/compose/.env` onto them.

## Core

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test` or `production`. Production refuses unsafe settings (see Security). |
| `PRODUCT_NAME` | `Euron GraphRAG` | Shown in the web app and the API docs. |
| `LOG_LEVEL`, `LOG_FORMAT` | `info`, `json` | `debug` to `error`; `json` or `console`. |
| `WEB_URL`, `API_URL` | localhost:3200, localhost:8200 | Used for CSRF origin checks and links. |
| `CORS_ORIGINS` | the two localhost origins | Comma separated; `*` is refused in production. |

## Data stores

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | local Postgres | `postgresql+asyncpg://...`. On AWS the URL has no password. |
| `DATABASE_SECRET_ARN` | unset | Secrets Manager secret read for each new connection, so a rotation needs no redeploy. |
| `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` | 10, 10 | Connection pool. |
| `MIGRATE_ON_BOOT` | false | The API applies migrations when it starts (Compose sets it). |
| `REDIS_URL` | local Valkey | Caches, rate limits, session revocation, leases. |

## Accounts

| Variable | Default | Meaning |
| --- | --- | --- |
| `SESSION_SECRET`, `API_KEY_PEPPER` | dev values | Random, at least 32 characters, different from each other in production. |
| `SESSION_TTL_HOURS` | 168 | Session lifetime. |
| `COOKIE_SECURE`, `COOKIE_DOMAIN` | false, unset | Set `COOKIE_SECURE` behind HTTPS. |
| `ALLOW_SIGNUP` | false | Whether anyone can create an account. The first account on a new instance is always allowed and becomes the administrator. |

## Storage and jobs

| Variable | Default | Meaning |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local` | `s3` or `local` (a directory, development only). |
| `S3_BUCKET`, `S3_KMS_KEY_ID` | unset | Originals bucket and its KMS key. |
| `AWS_REGION`, `AWS_ENDPOINT_URL` | us-east-1, unset | The endpoint override points at Floci locally and is refused in production. |
| `QUEUE_BACKEND` | `inline` | `sqs` (the worker takes jobs) or `inline` (the API runs them itself). |
| `SQS_QUEUE_URL` | unset | Required for `sqs`. |
| `WORKER_CONCURRENCY` | 2 | Jobs one worker runs at once. |
| `JOB_TIMEOUT_S`, `STALE_JOB_MINUTES` | 900, 15 | Per-job limit; when the reaper restarts unfinished work. |
| `MAX_UPLOAD_MB`, `MAX_DOCUMENT_PAGES` | 25, 2000 | Upload and parse limits. |
| `URL_FETCH_ALLOW_PRIVATE`, `URL_FETCH_TIMEOUT_S` | false, 20 | URL sources; private addresses are refused unless allowed (development only). |

## Providers

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `local` | `local`, `openai` (any OpenAI-compatible API) or `ollama`. |
| `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `OLLAMA_URL` | | The model for extraction, reports and answers. |
| `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT_S` | 0, 1200, 90 | Completion settings. |
| `EMBEDDING_PROVIDER` | `local` | `local` (feature hashing), `openai` or `ollama`. |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM` | , 384 | Width must be 384, 768, 1024 or 1536. |
| `EMBEDDINGS_API_BASE`, `EMBEDDINGS_API_KEY` | OpenAI base, unset | For `openai` embeddings. |
| `EMBEDDING_CACHE_TTL_S`, `EMBEDDINGS_BATCH_SIZE` | 30 days, 64 | Embedding cache and batching. |

Changing the embedding model or width does not rewrite existing vectors. Queries compare only
rows of the configured width, so re-process documents (and rebuild) after a change.

## Serving

| Variable | Default | Meaning |
| --- | --- | --- |
| `QUERY_CACHE_TTL_S` | 300 | How long an identical question is served from cache; any graph change retires it. |
| `QUERY_LOG_TEXT` | true | Store question text in the history; false stores it empty. |
| `RATE_LIMIT_LOGIN`, `_QUERY`, `_INGEST`, `_BUILD` | 10, 600, 120, 30 | Requests per minute per principal. |
| `TOKENIZER` | `tiktoken` | Or `heuristic` for an air-gapped host. |
| `DEMO_PASSWORD` | unset | Used only by `graphrag demo seed`. |

## Per project

Owners set these under Settings, Graph pipeline (stored in `projects.settings`): the entity
types the extractor may emit, `chunk_tokens` (60 to 800) and `overlap_tokens`, the number of
community levels (1 to 4), the Louvain `resolution` (0.2 to 3, higher gives smaller
communities) and whether builds start automatically after ingestion. They apply to documents
ingested afterwards; reprocess a document to apply them to it.

## Web app

The web container reads `API_URL` and `PRODUCT_NAME` at start and serves them at `/env.js`, so
one image serves every environment.
