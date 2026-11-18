"""Entity and relation extraction behind one interface."""

from __future__ import annotations

from graphrag.ai.llm import ChatClient
from graphrag.graph.extraction.contracts import Extractor
from graphrag.graph.extraction.llm import LlmExtractor
from graphrag.graph.extraction.local import RuleExtractor


def build_extractor(client: ChatClient | None, max_tokens: int) -> Extractor:
    """The model extractor when a model is configured, else the deterministic one."""
    return LlmExtractor(client, max_tokens) if client is not None else RuleExtractor()
