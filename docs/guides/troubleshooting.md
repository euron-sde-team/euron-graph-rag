# Troubleshooting

## Starting the stack

| Symptom | Cause | Fix |
| --- | --- | --- |
| `docker ps` fails (macOS) | The Docker engine is not running | Start Docker Desktop, or `colima start`. |
| `make up` is slow the first time | Images build and Terraform provisions the emulator | Wait; later starts reuse the build cache and the `graphrag-tf-plugins` volume. |
| The Terraform container fails with `releases.hashicorp.com: unexpected EOF` | A network flake while fetching providers | Run `make up` again. |
| A port is already in use | Another stack uses 3200, 8200, 5460, 6420 or 4620 | Change `GRAPHRAG_*_PORT` in `deploy/compose/.env` or stop the other stack. |
| `run make env first` | `deploy/compose/.env` is missing | `make env` (or `make up`, which runs it). |
| The API or the worker restarts or is `unhealthy` | Usually memory, or the database is not ready | `make logs SERVICE=api`; give Docker at least 4 GB. |

## Documents

| Symptom | Cause | Fix |
| --- | --- | --- |
| A document stays queued | The worker is not running or cannot reach SQS | `make ps`, `make logs SERVICE=worker`. |
| `This file has no text.` | A scanned PDF or an empty file | OCR it first; the parser reads text only. |
| `payload_too_large` | The file exceeds `MAX_UPLOAD_MB` | Raise the limit or split the file. |
| An upload is reported as a duplicate | A file with the same bytes is already in the project | Intended; the existing document is returned. |
| A URL is refused | It resolves to a private address, or is not http(s) | Use a public address; `URL_FETCH_ALLOW_PRIVATE=true` is for development only. |
| `duplicate_external_id` | Two sources share an `external_id` | Give each source a distinct id or omit it. |

## The graph

| Symptom | Cause | Fix |
| --- | --- | --- |
| Few entities, many documents | The rule extractor finds capitalized names and known concept terms; lowercase concepts are missed | Use a model (`LLM_PROVIDER`) or extend `graph/extraction/lexicon.py`. |
| An entity has the wrong type | The type is a vote across sentences | Edit it in the entity panel (type is editable). |
| Two names for one thing are not merged | Rules are conservative; an ambiguous short name is skipped | Entities, Duplicates tab, or merge them from the API. |
| No communities | No build has run, or the graph has no connected entities | Documents page, Rebuild communities. |
| Communities look too coarse or too fine | The Louvain resolution | Settings, Graph pipeline, Resolution and Levels, then rebuild. |
| A document's facts did not change after editing settings | Settings apply to documents ingested afterwards | Process the document again. |

## Questions

| Symptom | Cause | Fix |
| --- | --- | --- |
| "The knowledge graph has no passages that answer this question." | No sentence in the retrieved sources shares enough terms with the question (the offline composer quotes, it does not infer) | Rephrase, use hybrid, or configure a model. |
| Global answers are generic | No report matched the question and the most central communities were used | Ask about something the corpus names, or use local or hybrid. |
| `502 upstream_error` | The model provider could not be reached or timed out | Check `LLM_BASE_URL`, `LLM_API_KEY`, `OLLAMA_URL`; the offline provider needs none. |
| An answer cites a source that does not support it | A model wrote the answer | Read the source card; use `LLM_PROVIDER=local` for quoted answers. |
| `429 rate_limited` | Over the per-minute limit | Wait for `Retry-After`. |

## Browser and API

| Symptom | Cause | Fix |
| --- | --- | --- |
| The web app says GraphRAG is unreachable | The API is down or `API_URL` is wrong for the browser | `make ps`; the web container serves `API_URL` at `/env.js`. |
| `Cross-site request blocked` (403, `csrf`) | A cookie-authenticated write came from another origin | Use the configured web origin or a bearer token. |
| Sign-in loops back to the login page | The session cookie was not stored | Check `COOKIE_SECURE` (only behind HTTPS) and `COOKIE_DOMAIN`. |
| Integration tests cannot connect | Postgres, Valkey or Floci is not up | `scripts/test-deps.sh` (or `make test-integration`, which runs it). |

## Disk and memory (laptops)

Colima and Docker Desktop keep image and build caches; `make down` removes the stack's
containers and volumes but not images. `docker system df` shows what is reclaimable.
