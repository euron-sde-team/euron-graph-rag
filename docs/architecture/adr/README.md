# Architecture decision records

Short records of the decisions that shaped GraphRAG: the context, the choice and what it costs.
A change that alters one of them updates or supersedes its record.

| ADR | Decision |
| --- | --- |
| [0001](0001-postgres-and-pgvector-as-the-graph-store.md) | PostgreSQL and pgvector are the graph store |
| [0002](0002-louvain-with-a-hierarchy-for-communities.md) | Louvain with a connectivity guarantee and a hierarchy for communities |
| [0003](0003-deterministic-local-providers-first.md) | A deterministic local provider for extraction, reports and answers |
| [0004](0004-derived-counts-and-evidence-rows.md) | Counts and weights are derived from evidence rows, never incremented |
| [0005](0005-conservative-entity-resolution.md) | Conservative, explainable entity resolution rules |
| [0006](0006-floci-for-local-aws.md) | Floci provides AWS locally, provisioned by the production Terraform |
| [0007](0007-one-queue-for-parse-extract-and-build-jobs.md) | One queue for parse, extract and build jobs |
