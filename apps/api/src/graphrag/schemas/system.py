from __future__ import annotations

from typing import Any

from graphrag.schemas.common import ApiModel


class ProviderInfo(ApiModel):
    provider: str
    model: str
    deterministic: bool


class SystemInfo(ApiModel):
    product_name: str
    version: str
    extractor: ProviderInfo
    reporter: ProviderInfo
    answerer: ProviderInfo
    embedding: dict[str, Any]
    supported_dims: list[int]
    search_modes: list[str]
    entity_types: list[str]
    max_upload_mb: int
    accepted_extensions: list[str]
    allow_signup: bool
    needs_setup: bool
