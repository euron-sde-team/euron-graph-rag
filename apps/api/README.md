# GraphRAG API and worker

FastAPI service for Euron GraphRAG, plus the job worker (parse, extract and build jobs) that runs
from the same image with a different command.

```bash
uv sync
uv run pytest tests/unit -q                       # unit tests, no services
uv run pytest tests/integration -q -m integration # needs Postgres, Valkey, Floci (scripts/test-deps.sh)
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run graphrag --help                            # migrate, user create, demo seed, graph rebuild, openapi
uv run uvicorn graphrag.main:create_app --factory --port 8200
python -m graphrag.worker                         # needs QUEUE_BACKEND=sqs
```

## Layout and rules

```text
src/graphrag/
  api/          routes (URL, request and response models, access dependency) and deps
  services/     business rules, transactions, cache invalidation
  repositories/ the only code that touches the database
  graph/        pure domain code: extraction, resolution, communities, reports, search composition
  ai/           embedding providers, chat clients, tokenizer
  ingestion/    parsers, cleaning, chunking
  integrations/ storage, queue, URL fetcher, AWS clients
  core/         settings, errors, logging, security, rate limits, metrics
  models/ schemas/ migrations/ demo/
```

- A route calls one service and returns a schema; it never queries.
- Every repository method that reads project data takes the project id and filters by it.
- Graph writers (extraction, merges, entity edits, document deletion) take
  `GraphRepository.lock(project_id)` first; counts are derived by `recount`, never incremented.
- New settings go in `core/config.py` and `docs/guides/configuration.md`; schema changes are new
  Alembic revisions.
- Anything that calls a model has a deterministic local implementation behind the same interface.
