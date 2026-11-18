# Testing

| Layer | Command | What it covers |
| --- | --- | --- |
| API unit | `make test` (pytest) | Extraction, resolution, communities, reports, answer composition, embeddings, parsers, chunkers, security, config, the queue. No services needed. |
| Web unit | `make test` (Vitest) | Graph layout and view helpers, text and citation helpers, API client, formatting, runtime config. |
| API integration | `make test-integration` | The real pipeline on PostgreSQL with pgvector, Valkey and Floci: ingestion, graph reads and edits, builds, search in three modes, access control, the SQS worker, the reaper, the demo seed. |
| End to end | `make e2e` (Playwright, Chromium) | Journeys in the browser against the running stack. |
| QA crawl | `make qa` | Every page at 1440x900 and 390x844: console errors, failed requests, 4xx and 5xx, sideways scroll, broken links, serious axe violations. Full-page captures in `e2e/.qa/` to review. |
| Screenshots | `make screenshots` | README images at 1440x900 and 2x, plus the tour GIF. |
| Static | `make lint typecheck` | ruff, mypy (strict), ESLint, Prettier, tsc. |
| Infrastructure | `make tf-fmt tf-validate tf-lint tf-security` | Terraform format and validate for all three environments, tflint, checkov. |

## Integration suite

`scripts/test-deps.sh` starts Postgres, Valkey and Floci from the Compose files if they are not
running. The suite creates its own database (`graphrag_test`, dropped and recreated each run),
uses Valkey database 15 and makes uniquely named buckets, keys and queues on the emulator, so
a development stack's data is never touched. Override the targets with
`TEST_DATABASE_ADMIN_URL`, `TEST_REDIS_URL` and `TEST_AWS_ENDPOINT_URL`.

Most tests share one session fixture: the demo notes ingested once through the real pipeline
(`graph` in `tests/integration/conftest.py`). Tests that change data build their own small
project. The inline queue runs jobs in the API process, and `settle()` waits for every job
including the jobs they enqueue; the worker tests use real SQS instead.

## Writing tests

- Put pure logic in `graph/`, `ai/` or `ingestion/` and test it without services.
- Test behaviour that crosses a boundary (SQL, the queue, HTTP) in the integration suite, with
  real services, not mocks.
- Use `example.com` addresses for test accounts.
- A browser test signs in through `signIn(page, role)`, which reuses a saved session per role;
  the API limits sign-ins per minute.

## What the numbers mean

The README lists the current counts. Coverage of the domain packages (`graph/`, `ai/`,
`ingestion/`) is measured with `uv run pytest --cov` in `apps/api`.
