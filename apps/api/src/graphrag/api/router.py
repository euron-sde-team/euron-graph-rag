from __future__ import annotations

from fastapi import APIRouter

from graphrag.api.routes import (
    api_keys,
    auth,
    communities,
    documents,
    graph,
    health,
    overview,
    projects,
    search,
)

api_router = APIRouter()
for module in (health, auth, projects, documents, graph, communities, search, overview, api_keys):
    api_router.include_router(module.router)
api_router.include_router(communities.builds)
