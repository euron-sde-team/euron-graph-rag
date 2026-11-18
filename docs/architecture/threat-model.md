# Threat model (STRIDE)

Scope: the API, the worker, the web app and their data stores in a normal deployment (AWS or the
local Compose stack). Assets: documents and the graph derived from them (often confidential),
accounts and API keys, model provider credentials, availability of the pipeline.

Trust boundaries: browser to API, API clients to API, API and worker to the model provider, the
worker to arbitrary URLs, API and worker to data stores.

| ID | Threat | STRIDE | Mitigation | Residual risk |
| --- | --- | --- | --- | --- |
| T1 | Guessing passwords or enumerating accounts | Spoofing | Argon2id, dummy hash for unknown emails, lockout, per-address rate limit that fails closed | Distributed guessing below the limits |
| T2 | Stolen session cookie or token | Spoofing | `httponly` `SameSite` cookie, signed JWT with issuer and audience, `session_version` and revocation list, HTTPS and `Secure` in production | A stolen token works until expiry or sign-out |
| T3 | Leaked API key | Spoofing | Only an HMAC of the secret is stored, project-bound, role-limited, expirable, revocable, `last_used_at` visible | A leaked live key works until revoked |
| T4 | Cross-site request forgery on cookie sessions | Spoofing, Tampering | Origin or Referer must match the web origin for unsafe methods; CORS allowlist | None known |
| T5 | Reading or changing another project's graph | Information disclosure, Tampering | Every query filters on the resolved project, outsiders get 404, ids from other projects resolve to nothing, tests assert it | Bugs in new queries; the integration suite covers every route family |
| T6 | A viewer or a read-only key changing data | Elevation of privilege | Role dependency on every route, 403 tests per write route | None known |
| T7 | Malicious document (zip bomb, huge PDF, hostile markup) | Denial of service, Tampering | Size limits, page and uncompressed caps, sniffing, parsers run in a worker thread with a job timeout, HTML is parsed to text, never rendered | A crafted file can still waste the worker's CPU until the timeout |
| T8 | URL source pointing at internal services (SSRF) | Information disclosure | Scheme allowlist, DNS resolved and every address checked, redirects re-checked, size and time limits, private ranges refused in production | DNS rebinding between check and connect is narrowed by connecting to the checked address only |
| T9 | Prompt injection in a document steering a model extractor, reporter or answerer | Tampering | Models only produce structured data that is validated and normalized; answers cite sources; the local provider has no instructions to hijack; no tool use | A hosted model can still be misled into a wrong fact; citations let a reader check |
| T10 | A wrong entity merge corrupting the graph | Tampering | Merge rules are conservative and deterministic (ambiguous matches are skipped), a preview endpoint, audit events, entities keep merged names as aliases | A bad merge needs a manual rename and re-extract |
| T11 | Cache poisoning across projects | Information disclosure | All cache keys include the project; answers include `graph_version` | None known |
| T12 | Secrets in logs, errors or API responses | Information disclosure | Log redaction, errors carry code, message and request id only, secrets are `SecretStr`, keys shown once | Operators must not log request bodies in front proxies |
| T13 | Queue message tampering or replay | Tampering | Messages hold ids only, handlers re-read rows and are idempotent, SQS access is limited to the task roles | None known |
| T14 | Exhausting the API or the worker | Denial of service | Rate limits per principal for queries, ingestion and builds, body size limit, bounded concurrency, builds coalesce per project, dead-letter queue | A tenant with a valid key can use its quota |
| T15 | Repudiation of destructive actions | Repudiation | Audit trail for members, keys, documents, entity edits, merges and builds with the acting user or key | The trail is in the same database |
| T16 | Supply chain (images, packages) | Tampering | Pinned base images and lockfiles, gitleaks, checkov, CI scans, non-root containers | Upstream compromise before a pin is updated |

## Data flow summary

1. Browser to API: TLS, cookie or bearer, CSRF origin check, role check, project check.
2. API to Postgres: parameterized queries through SQLAlchemy, project filters in every repository.
3. Worker to URLs: SSRF guard on every request and redirect.
4. API and worker to model providers: only when configured; passages leave the deployment then.
5. Worker to Postgres and S3: same filters, KMS-encrypted originals.

## Out of scope

Compromise of the cloud account, of the database host or of a maintainer's machine; side
channels inside the model provider; content moderation of what users upload.
