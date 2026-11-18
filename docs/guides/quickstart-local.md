# Quickstart: run it locally

Everything runs in Docker Compose on your machine. No cloud account and no API key: AWS is
emulated by Floci and every model task has a deterministic local implementation.

## Prerequisites

- Docker with Compose v2 (Docker Desktop, Colima, Rancher Desktop) and about 4 GB of free memory
- `make`
- For development outside Docker: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 and
  pnpm 9

## Start the stack

```bash
make up      # builds the images, starts Postgres, Valkey, Floci, the API, the worker and the web app
make demo    # accounts, a project, eighteen research notes, the graph and two weeks of questions
```

`make up` generates `deploy/compose/.env` with random local secrets the first time. The first
start also builds the images and applies Terraform against Floci, which takes a few minutes.

When it finishes:

| What | Where |
| --- | --- |
| Web app | http://localhost:3200 |
| API and docs | http://localhost:8200/docs |
| PostgreSQL | `localhost:5460` (user, password and database `graphrag`) |
| Valkey | `localhost:6420` |
| Floci (AWS emulator) | `http://localhost:4620` |

`make demo` prints the three demo accounts and their shared password, and an API key:

| Account | Role |
| --- | --- |
| `maya.iyer@meridian-research.example` | owner |
| `lucas.moreau@meridian-research.example` | editor |
| `hana.takeda@meridian-research.example` | viewer |

The demo ingests the notes through the real worker, so it takes a minute or so; the project is
**Port Intelligence**, an analyst notebook on autonomous port logistics.

## Try it

1. Open the web app and sign in as Maya. The overview shows the graph at a glance.
2. **Graph explorer**: click Helios Robotics; read its relations and source passages.
3. **Communities**: open a community, read its report and findings.
4. **Playground**: ask "Who founded Helios Robotics?" in local mode, then "How is predictive
   maintenance used in port terminals?" in global mode.
5. **Documents**: add a note (Add documents, Text) and watch it move through the pipeline into
   the graph.

Or from the shell, with the key `make demo` printed:

```bash
curl -s http://localhost:8200/api/v1/projects/port-intelligence/query \
  -H "authorization: Bearer grk_..." -H "content-type: application/json" \
  -d '{"question": "Who founded Helios Robotics?", "mode": "local"}'
```

## Stop and reset

```bash
make down    # stops the stack and deletes its volumes (the Terraform provider cache is kept)
```

## Use a real model (optional)

Add to `deploy/compose/.env`, then `make up`:

```bash
GRAPHRAG_LLM_PROVIDER=ollama
GRAPHRAG_LLM_MODEL=llama3.2
GRAPHRAG_EMBEDDING_PROVIDER=ollama
GRAPHRAG_EMBEDDING_MODEL=nomic-embed-text
GRAPHRAG_EMBEDDING_DIM=768
```

With a model, extraction, community reports and answers come from it; unusable replies fall
back to the local implementation for that chunk or report. See
[configuration](configuration.md).

## Develop outside Docker

```bash
make test               # unit tests: pytest and Vitest
make test-integration   # starts Postgres, Valkey and Floci and runs the API integration suite
make lint typecheck     # ruff, ESLint, Prettier, mypy, tsc
pnpm dev                # the web app on :3200 against a running API
```
