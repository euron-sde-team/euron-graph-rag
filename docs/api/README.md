# API reference

The OpenAPI 3.1 document generated from the application is [`openapi.json`](openapi.json)
(`make openapi` regenerates it; CI checks it is current). A running API serves the same
document and an interactive page at `/docs`.

## Authentication

- **Browser sessions**: `POST /api/v1/auth/login` sets an `httponly` cookie. Writes must come
  from the web origin (CSRF check).
- **Bearer**: `Authorization: Bearer <session token>` from login, or a project API key
  (`grk_<prefix>_<secret>`) created under Settings, API keys. A key is bound to one project and
  is a viewer (read and ask) or an editor (also ingest, edit the graph, request builds).

## Conventions

- Base path `/api/v1`; project routes live under `/api/v1/projects/{project}` where `{project}`
  is the slug or the id.
- Lists are paged with `limit` and `offset` and return `{items, total, limit, offset}`.
- Errors: `{"error": {"code", "message", "request_id", "details?"}}`. Every response has an
  `X-Request-Id` header; quote it when reporting a problem.
- Rate limits answer `429` with `Retry-After` and `X-RateLimit-*` headers.

## Route groups

| Group | Examples |
| --- | --- |
| auth | `POST /auth/login`, `GET /auth/me`, `POST /auth/password` |
| projects | `GET /projects`, `PATCH /projects/{p}` (name, description, graph settings), `GET /projects/{p}/members`, `GET /projects/{p}/activity` |
| documents | `POST /documents` (multipart files), `POST /documents/import` (text and URL sources), `GET /documents`, `GET /documents/{id}/chunks`, `POST /documents/{id}/reprocess`, `DELETE /documents/{id}` |
| graph | `GET /graph/entities`, `GET /graph/entities/{id}`, `PATCH` and `DELETE` on an entity, `GET /graph/explore`, `GET /graph/duplicates`, `POST /graph/merge` |
| communities | `GET /communities`, `GET /communities/tree`, `GET /communities/{id}` |
| builds | `GET /builds`, `POST /builds` (202), `GET /builds/{id}` |
| search | `POST /query`, `GET /queries`, `GET /queries/{id}` |
| overview | `GET /overview` |
| api keys | `GET`/`POST /api-keys`, `DELETE /api-keys/{id}` |
| system | `GET /api/v1/system/info`, `/livez`, `/readyz`, `/metrics` |

## Ask a question

```bash
curl -s http://localhost:8200/api/v1/projects/port-intelligence/query \
  -H "authorization: Bearer $GRAPHRAG_KEY" -H "content-type: application/json" \
  -d '{"question": "Who founded Helios Robotics?", "mode": "local", "top_k": 6, "hops": 1}'
```

The response holds the `answer` (with `[n]` markers), every `citations` entry (`kind` chunk or
community, `cited`, a `snippet`, and for a community the chunk ids it is `supports`), the
`nodes` and `edges` used, the `communities` used with their points, the `steps` with
timings and the token counts when a model answered.
