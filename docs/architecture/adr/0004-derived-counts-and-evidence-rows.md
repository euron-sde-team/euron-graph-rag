# 0004: Counts and weights are derived from evidence rows, never incremented

Status: accepted

## Context

An entity's mention count, a relation's weight and evidence count and every degree change when
a document is added, reprocessed, deleted or when entities merge. Incrementing counters in
place drifts under retries, duplicate deliveries and partial failures.

## Decision

Store facts as rows: `entity_mentions` (entity, chunk, count) and `relation_evidence` (relation,
chunk, quote). Derive `mention_count`, `evidence_count`, `weight`, `degree` and `importance` from
them with set-based SQL (`recount`, `refresh_degrees`) after any change. Re-extracting a document
first deletes its earlier mentions and evidence. Entities nobody mentions and relations nobody
supports are deleted by the same pass.

## Consequences

- Reprocessing is idempotent: the counts after a second run equal the first.
- Deleting a document removes exactly what only it supported.
- Merges reduce to moving rows and recounting.
- Every number on screen can be traced to rows, and every row to a passage.
- The recount touches a project's rows; it is one UPDATE per table and stays fast at the sizes
  of one project.
