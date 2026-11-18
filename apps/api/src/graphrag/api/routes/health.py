"""Probes, metrics and public deployment capabilities."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from graphrag import __version__
from graphrag.api.deps import ContainerDep, SessionDep
from graphrag.core.logging import get_logger
from graphrag.db.types import SUPPORTED_DIMS
from graphrag.ingestion.sniff import EXTENSIONS
from graphrag.models.enums import EntityType, SearchMode
from graphrag.repositories.users import UserRepository
from graphrag.schemas.system import ProviderInfo, SystemInfo

router = APIRouter()
log = get_logger("graphrag.health")


@router.get("/livez", include_in_schema=False)
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(container: ContainerDep) -> JSONResponse:
    checks: dict[str, Any] = {}
    for name, probe in (
        ("database", container.db.ping),
        ("redis", container.redis.ping),
        ("storage", container.storage.check),
        ("queue", container.queue.check),
    ):
        try:
            await probe()
            checks[name] = "ok"
        except Exception as exc:
            log.warning("readiness_check_failed", check=name, error=type(exc).__name__)
            checks[name] = "failing"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "degraded", "checks": checks},
        status_code=200 if ready else 503,
    )


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/v1/system/info", tags=["system"], summary="Deployment capabilities and limits")
async def system_info(container: ContainerDep, session: SessionDep) -> SystemInfo:
    settings = container.settings
    client = container.chat_client

    def provider(local_model: str) -> ProviderInfo:
        if client is None:
            return ProviderInfo(provider="local", model=local_model, deterministic=True)
        return ProviderInfo(
            provider=client.provider, model=client.default_model, deterministic=False
        )

    return SystemInfo(
        product_name=settings.product_name,
        version=__version__,
        extractor=provider("rule-based"),
        reporter=provider("template"),
        answerer=provider("extractive"),
        embedding=container.embedders.spec.public(),
        supported_dims=list(SUPPORTED_DIMS),
        search_modes=[m.value for m in SearchMode],
        entity_types=[t.value for t in EntityType],
        max_upload_mb=settings.max_upload_mb,
        accepted_extensions=sorted(EXTENSIONS),
        allow_signup=settings.allow_signup,
        needs_setup=await UserRepository(session).count() == 0,
    )
