# Low-Level Design

How the pieces work: layering, the pipeline stages, the graph algorithms, search and the
queue. Names are those of the Python package `graphrag` under `apps/api/src/graphrag`.

## Layering

```text
api/routes  ->  services  ->  repositories  ->  PostgreSQL
   (URL, auth)   (rules, transactions,   (the only code that
                  cache invalidation)     touches the database)
graph/*, ai/*, ingestion/*: pure domain code with no I/O
```

- `api/deps.py` resolves the caller (cookie session or bearer token or API key), the project
  and the minimum role (`ViewerDep`, `EditorDep`, `OwnerDep`).
- `services/` hold business rules: `documents`, `ingestion` (parse), `extraction`, `builds`,
  `graph`, `communities`, `search`, `overview`, plus accounts, projects, keys and audit.
- `repositories/` expose queries: `documents`, `chunks`, `graph`, `communities` (and builds),
  `queries`, and the account repositories.
- `graph/` is the domain without I/O: `names`, `extraction/`, `resolution`, `communities`,
  `summaries`, `search/`. It is unit tested without services.
- `core/` has validated settings, errors, logging, request context, security, rate limiting
  and metrics. `integrations/` has storage (S3 or local), the queue (SQS or inline), the URL
  fetcher and AWS clients.

## The pipeline

### Parse (job `parse`)

1. Claim the document row `FOR UPDATE`; a claim younger than two minutes means another worker
   has it, so a duplicate delivery is dropped.
2. Load the original from storage (or fetch the URL and keep a snapshot), parse it with the
   parser of its kind (PDF, DOCX, Markdown, HTML, text, CSV) into sections of blocks.
3. Clean (Unicode, whitespace), chunk with the recursive strategy (structure first, token
   windows with overlap, headings travel with the text they introduce) using the project's
   `chunk_tokens` and `overlap_tokens`.
4. Embed `title + heading + text` of each chunk through the cached embedder.
5. In one transaction: replace the document's sections and chunks, update counts, set the
   stage to `extracting` and enqueue the `extract` job.

### Extract (job `extract`)

The extractor receives all chunks of one document and the project's entity types and returns,
per chunk, entities (name, type, description, count) and relations (source, target, predicate,
quote, weight).

- **Rule extractor** (`graph/extraction/local.py`): finds capitalized names and a lexicon of
  concept terms; types them by votes across the document (titles, organization and product
  suffixes, first names, place gazetteer, acronyms, the verbs around a name); links two
  entities in one sentence through an ordered table of verb patterns with type constraints
  (`FOUNDED`, `ACQUIRED`, `PARTNERED_WITH`, `LEADS`, `LOCATED_IN` and so on). Passive voice
  reverses the edge; "A acquired B and partnered with C" gives C to A. An untyped entity takes
  the type a pattern requires. Sentences never cross a line break, so headings do not glue to
  the next sentence.
- **Model extractor** (`graph/extraction/llm.py`): one completion per chunk, a JSON reply
  parsed leniently (code fences, prose, truncation), types and predicates normalized, relation
  endpoints added as entities when the model forgot them. A chunk whose reply cannot be parsed
  uses the rule extractor.

The result is written in one transaction (`services/extraction.py`):

1. Aggregate entities across the document (type by weighted vote, the description that best
   introduces the entity).
2. Look every name up in the project's **alias index** (primary keys plus merged aliases);
   unseen names become entities with a name-and-description embedding.
3. Delete this document's earlier mentions and evidence, insert the new ones (an entity per
   chunk with a count; a relation evidence row per sentence that stated it).
4. `recount`: relation `evidence_count` and `weight` and entity `mention_count` are derived
   from evidence and mention rows; entities nobody mentions and relations nobody supports are
   deleted. `refresh_degrees` sets degree and importance.
5. Mark the document `ready`, bump `projects.graph_version`, queue a build if none is waiting.

### Build (job `build`)

`services/builds.py`:

1. Claim the build; wait (outside the inline queue) until no document of the project is still
   processing, so a batch of uploads is built once.
2. **Resolve duplicates** (`graph/resolution.py`): rules in order, alias, fuzzy spelling
   (SequenceMatcher ratio at least 0.9, same type and token count), containment (a name that
   starts or ends another, exactly one candidate after counting fuzzy groups once) and acronym
   (initials). Union-find; the survivor is the most mentioned, then the longest. The merge moves
   mentions (folded per chunk before the upsert), re-points relations (dropping self loops and
   collapsing twins, moving their evidence) and keeps the victims' names as aliases.
3. **Detect communities** (`graph/communities.py`): see below.
4. **Write reports** bottom-up with the reporter (template or model), embed each
   `title. summary`, and replace all communities and members in one transaction.
5. Record statistics (entities, relations, merges, communities per level, modularity,
   isolated entities) on the build row.

## Community detection

Louvain modularity optimization with a seeded visiting order and sorted ties, so the same
graph always yields the same partition. Nodes move to the neighbouring community with the best
modularity gain; communities collapse into nodes (internal weight stays as a self loop, which
the gain formula needs) and the pass repeats until nothing moves.

Two additions give it the behaviour of GraphRAG's hierarchical Leiden:

- **Connectivity guarantee**: a community that is not connected is split into its connected
  components.
- **Hierarchy**: level 0 is the partition of the whole graph; each community larger than
  `split_above` (six) is partitioned again on its own subgraph with a slightly higher
  resolution, singletons absorbed into the neighbour they share the most weight with, down to
  the project's `community_levels`. A community that does not split has no children and stands
  for itself at deeper levels (`communities_at`). Isolated entities belong to no community.

## Reports

`LocalReporter` writes from templates: the title names the three most important entities, the
summary opens with the lead entity's description, lists the strongest relations and counts the
members; findings are the strongest relations with the sentence that stated them and the chunks
that evidence them. `LlmReporter` asks a model for the same JSON structure from the same
inputs, attaches chunk ids to a finding by matching the relations it names and falls back to
the template on an unusable reply.

## Search

`services/search.py`, building on `graph/search/`.

**Local.** Seeds: entities whose key appears in the question (a SQL `LIKE` on the key), entities
whose embedding is close (`0.3 + 0.7 x cosine`, above a floor) and entities in the three best
vector passages (0.35). The best eight seed. Expansion walks relations for `hops` rounds,
decaying scores by 0.6 per hop, capped at 48 nodes. Candidate passages are the vector and
keyword hits, passages mentioning seeds and passages that evidence chosen edges; each is scored
`0.45 x similarity + 0.20 x keyword + 0.25 x seed coverage + 0.10 x edge coverage`. The best
`top_k` become numbered sources.

**Global.** Pick the level (default 1, never deeper than exists), take `communities_at(level)`,
score each report `0.5 x cosine + 0.5 x term overlap`, map the best 24 to points (sentences of
the report scored against the question, or a model's JSON points) and reduce the best points
into community sources. A question that shares no word with any report (a broad question)
falls back to the most central communities, and the answer is a digest of their openings.

**Hybrid.** Local sources first, then the three strongest community sources.

**Answers.** Offline, the extractive composer scores every sentence of the sources against the
question (idf weighted overlap), keeps those within 55% (local) or 25% (global) of the best and
prints them in source order, each followed by its citation. With a model, the sources are
numbered in the prompt and invalid citation markers are removed from the reply. Either way the
response lists every source with `cited` true or false, so the UI can show what was retrieved
but not used.

**Cache.** `q:{project}:{graph_version}:{sha256(mode, question, params, extractor)}` for the
query TTL. Any change to chunks, entities, relations or communities bumps `graph_version`,
retiring cached answers without a scan.

## Queue and worker

`integrations/queue.py` has `Job(kind, project_id, document_id|build_id)` with three kinds and
two implementations: `SqsQueue` (long polling, visibility extended by a heartbeat, dead-letter
after three receives) and `InlineQueue` (one background runner in the API process, used in
development without a worker and in tests). The worker (`worker.py`) runs up to
`WORKER_CONCURRENCY` jobs, hands unfinished jobs back on SIGTERM and runs the reaper under a
Valkey lease: documents and builds stuck beyond `STALE_JOB_MINUTES` are re-sent (queued work
only while the queue is empty) or marked failed after three attempts.

## Embeddings and providers

`ai/embeddings.py`: `local` is signed feature hashing of stemmed words and word pairs
(deterministic, lexical, no model); `openai` and `ollama` call `/embeddings` and `/api/embed`.
Every vector is L2-normalized. The width is `EMBEDDING_DIM` (384, 768, 1024 or 1536) and
rows carry `embedding_dim`, so a width change does not corrupt old rows (they are skipped by
queries until reprocessed). `CachedEmbedder` keys Valkey by project, model, width and text hash.
`ai/llm.py` has the OpenAI-compatible and Ollama chat clients behind one `ChatClient` protocol.

## Frontend

Next.js App Router, React 19, TanStack Query (polling while work is in flight), Tailwind 4
tokens in `globals.css`. The explorer (`components/graph/force-graph.tsx`) is SVG: the layout
(`lib/graph.ts`, d3-force) is computed synchronously so the first paint is settled, then nodes
drag, the view pans and zooms, and every node is a focusable button. Labels follow importance.

## Errors, logging, metrics

`AppError` subclasses map to the error envelope; unexpected errors become a generic 500 with
the request id. Logs are JSON through structlog with the request id bound by middleware.
Metrics are listed in the [HLD](HLD.md#observability).
