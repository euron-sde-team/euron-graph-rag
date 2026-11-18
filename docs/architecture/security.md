# Security

What protects a GraphRAG deployment and where the controls live. The attacker's view is in the
[threat model](threat-model.md); reporting a vulnerability is covered in
[SECURITY.md](../../SECURITY.md).

## Authentication

- **Passwords**: Argon2id (`core/security.py`). Verification of an unknown email still hashes
  against a dummy value, so response time does not reveal which emails exist.
- **Sessions**: a signed JWT (issuer and audience pinned) in an `httponly`, `SameSite=Lax`
  cookie, or as a bearer token. Each user has a `session_version`; changing the password or
  signing out bumps it and every older token stops working. Signing out stores the token's id in
  Valkey, so that one token stops working at once.
- **Lockout**: repeated wrong passwords lock the account for a fixed interval; sign-in is
  rate limited per address and fails closed when the counter store is down.
- **API keys**: `grk_<prefix>_<secret>`; only an HMAC-SHA256 of the secret, keyed with a
  server pepper, is stored. Keys are bound to one project and carry editor or viewer role,
  optional expiry and revocation.

## Authorization

Every project route resolves the project through the caller's membership (or the key's project)
and requires a minimum role: viewers read and ask questions, editors change documents and the
graph and request builds, owners manage members, keys and settings. A project the caller does
not belong to answers 404, not 403, and ids from another project resolve to nothing because
every repository query filters on the project.

## Web and transport

- CSRF: unsafe cookie-authenticated requests must come from the configured web origin
  (`Origin`, else `Referer`); bearer and key requests carry no ambient credentials.
- CORS lists the web origin explicitly; production refuses `*`.
- Security headers on every response, HSTS in production, request body size limit (twenty
  files of the per-file limit plus overhead), strict request models (`extra="forbid"`).
- `/metrics` is meant for the private network; the AWS deployment keeps it off the load
  balancer's public listener.

## Data handling

- Uploaded originals go to S3 with SSE-KMS (local runs use the Floci emulator); keys are
  generated from ids, never from file names.
- URL sources are fetched by the worker through an SSRF guard: schemes limited to http(s),
  DNS resolved and every address checked against private, loopback and link-local ranges,
  redirects re-checked, size and time limits. `URL_FETCH_ALLOW_PRIVATE` exists for development
  and production refuses it.
- Uploads are sniffed against their extension, size limited and parsed with page and size
  caps (zip bombs, huge PDFs).
- Caches are keyed by project (and by `graph_version` for answers), so one project can never
  be served another's cached answer or embedding.
- Questions are stored for the history; `QUERY_LOG_TEXT=false` stores an empty question text.
- Secrets never appear in logs: structlog processors drop authorization and cookie values and
  API errors expose only a code, a message and the request id.

## Model providers

With a hosted provider configured, passages are sent to it for extraction, reports and
answers. The local provider sends nothing anywhere. A provider key lives in an environment
variable (a Secrets Manager reference on AWS), is held as a `SecretStr` and is never
returned by the API.

## Production configuration check

With `APP_ENV=production` the API refuses to start unless: secrets are random and at least 32
characters and differ from each other, cookies are secure, CORS is explicit, storage is S3,
the queue is SQS, no AWS endpoint override is set, URL fetching of private addresses is off
and a model name is set when a model provider is. All problems are reported at once.

## Container and infrastructure

Non-root images, pinned bases, read-only temp mounts, healthchecks, tini for signal handling.
Terraform: private subnets for data stores, security groups by source, KMS keys for S3, RDS
and SQS, Secrets Manager for credentials, ALB with HTTPS, optional CloudFront and WAF hooks.
`checkov` and `tflint` run in CI with each skip justified inline.
