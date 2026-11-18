# 0003: A deterministic local provider for extraction, reports and answers

Status: accepted

## Context

The product must run, be tested and be demoed with no account and no API key, and screenshots
must reproduce. Real language models are the better extractors, but they are slow, vary
between runs and need credentials.

## Decision

Every model-shaped task has a deterministic local implementation behind the same interface as
the model one: the rule extractor, the template reporter, the extractive answer composer and
the feature-hashing embedder. OpenAI-compatible and Ollama adapters implement the same
protocols. `LLM_PROVIDER` and `EMBEDDING_PROVIDER` choose; the default is local.

## Consequences

- Unit and integration tests, `make demo`, e2e and screenshots need no network.
- The local extractor is honest about being a baseline: it finds capitalized names and known
  concept terms and links them through verb patterns. It is documented as such, and a model
  extractor is a one-line configuration change for recall.
- The local answer composer quotes sources and cannot paraphrase or infer, which makes its
  citations trivially faithful.
- Model replies are validated and normalized, and fall back to the local implementation when
  unusable, so a model never leaves a hole in the graph.
