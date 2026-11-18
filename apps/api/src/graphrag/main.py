"""The FastAPI application factory.

uvicorn graphrag.main:create_app --factory --port 8200
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from graphrag import __version__
from graphrag.api.router import api_router
from graphrag.core.config import Settings, get_settings
from graphrag.core.context import BodySizeLimitMiddleware, RequestContextMiddleware
from graphrag.core.errors import install_exception_handlers
from graphrag.core.logging import configure_logging, get_logger
from graphrag.db.migrate import migrate
from graphrag.integrations.queue import InlineQueue
from graphrag.services.container import build_container
from graphrag.services.ingestion import IngestionService

log = get_logger("graphrag.app")

DESCRIPTION = """
Extract a knowledge graph from documents, summarize its communities and answer questions
over it with citations.

Authenticate with the session cookie set by `POST /api/v1/auth/login`, or with
`Authorization: Bearer <token>` using a session token or a project API key (`grk_...`).
Every error uses one envelope: `{"error": {"code", "message", "request_id", "details?"}}`.
"""

TAGS = [
    {"name": "auth", "description": "Sign-in, sign-up, sessions and your profile."},
    {"name": "projects", "description": "Projects (one knowledge graph each), members and roles."},
    {
        "name": "documents",
        "description": "Files, URLs and text: intake, chunks and ingestion state.",
    },
    {"name": "graph", "description": "Entities, relations, merges and the explorer view."},
    {"name": "communities", "description": "Hierarchical communities with generated reports."},
    {"name": "builds", "description": "Duplicate resolution, community detection and reports."},
    {"name": "search", "description": "Local, global and hybrid questions with citations."},
    {"name": "overview", "description": "Dashboard figures: graph size, pipeline and traffic."},
    {"name": "api keys", "description": "Project-scoped keys for applications and CI."},
    {"name": "system", "description": "Deployment capabilities and limits."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    if settings.is_production and (problems := settings.production_problems()):
        raise RuntimeError("Refusing to start in production:\n  - " + "\n  - ".join(problems))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.migrate_on_boot:
            await migrate(settings)
        container = build_container(settings)
        if isinstance(container.queue, InlineQueue):
            container.queue.bind(IngestionService(container).handle)
        app.state.container = container
        log.info(
            "started",
            version=__version__,
            env=settings.app_env,
            extractor=container.extractor.name,
            embedding=container.embedders.spec.key,
            queue=settings.queue_backend,
            storage=settings.storage_backend,
        )
        try:
            yield
        finally:
            if isinstance(container.queue, InlineQueue):
                await container.queue.drain()
            await container.close()

    app = FastAPI(
        title=settings.product_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
        license_info={"name": "MIT", "identifier": "MIT"},
    )
    install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-request-id"],
        expose_headers=[
            "x-request-id",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "content-disposition",
        ],
        max_age=600,
    )
    # Twenty files per upload request, each up to the per-file limit, plus form overhead.
    app.add_middleware(
        BodySizeLimitMiddleware, max_bytes=settings.max_upload_bytes * 20 + 1024 * 1024
    )
    app.add_middleware(RequestContextMiddleware, hsts=settings.is_production)
    app.include_router(api_router)
    return app
