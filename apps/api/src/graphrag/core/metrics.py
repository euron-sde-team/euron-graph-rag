"""Prometheus metrics, exposed at GET /metrics (and by the worker on WORKER_METRICS_PORT).

One API process per container (scale out with containers, not uvicorn workers), so the
default registry is accurate without multiprocess mode.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "graphrag_http_requests_total",
    "HTTP requests by route template.",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "graphrag_http_request_duration_seconds",
    "HTTP request latency by route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
DOCUMENTS_PARSED = Counter(
    "graphrag_documents_parsed_total", "Documents parsed by the worker.", ["kind", "outcome"]
)
CHUNKS_WRITTEN = Counter("graphrag_chunks_written_total", "Chunks written to the graph store.")
EXTRACTIONS = Counter(
    "graphrag_extractions_total",
    "Documents run through entity extraction.",
    ["extractor", "outcome"],
)
EXTRACTION_DURATION = Histogram(
    "graphrag_extraction_duration_seconds",
    "Extraction and persistence time per document.",
    ["extractor"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)
ENTITIES_WRITTEN = Counter("graphrag_entities_written_total", "Entity rows created or updated.")
RELATIONS_WRITTEN = Counter("graphrag_relations_written_total", "Relation rows created or updated.")
ENTITIES_MERGED = Counter(
    "graphrag_entities_merged_total", "Duplicate entities merged.", ["source"]
)
BUILDS = Counter("graphrag_builds_total", "Graph builds by outcome.", ["outcome"])
BUILD_DURATION = Histogram(
    "graphrag_build_duration_seconds",
    "Graph build time: resolution, community detection and summaries.",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 900),
)
QUERIES = Counter("graphrag_queries_total", "Questions answered by mode.", ["mode"])
QUERY_STAGE = Histogram(
    "graphrag_query_stage_seconds",
    "Query latency by stage: embed, seeds, expand, chunks, map, reduce, answer, total.",
    ["mode", "stage"],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 10),
)
CACHE = Counter("graphrag_cache_total", "Cache lookups by cache and result.", ["cache", "result"])
