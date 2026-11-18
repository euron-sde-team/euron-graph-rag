"""`graphrag demo seed` builds the demo project through the real pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from graphrag.core.config import Settings
from graphrag.demo.corpus import NOTES
from graphrag.demo.seed import PROJECT_SLUG, rebuild, run
from graphrag.models import Document, Entity, GraphBuild, QueryLog
from graphrag.services.container import build_container

pytestmark = pytest.mark.integration


async def test_the_seed_builds_a_lived_in_project_and_is_idempotent(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    await run(settings, "Demo-password-2026", traffic=True)
    first = capsys.readouterr().out
    assert "API key (viewer): grk_" in first and "maya.iyer@meridian-research.example" in first
    await run(settings, "Demo-password-2026", traffic=True)
    assert "already exists" in capsys.readouterr().out

    container = build_container(settings)
    try:
        async with container.db.session() as session:
            documents = await session.scalar(select(func.count()).select_from(Document))
            entities = await session.scalar(select(func.count()).select_from(Entity))
            oldest = await session.scalar(select(func.min(QueryLog.created_at)))
            queries = await session.scalar(select(func.count()).select_from(QueryLog))
            build = (
                await session.execute(
                    select(GraphBuild).order_by(GraphBuild.created_at.desc()).limit(1)
                )
            ).scalar_one()
    finally:
        await container.close()
    assert documents is not None and documents >= len(NOTES)
    assert entities is not None and entities >= 40
    assert queries is not None and queries >= 30
    assert oldest is not None and oldest < datetime.now(UTC) - timedelta(days=10)
    assert build.status == "completed"


async def test_a_rebuild_can_be_queued_from_the_command_line(settings: Settings) -> None:
    assert await rebuild(settings, PROJECT_SLUG) is True
    assert await rebuild(settings, "no-such-project") is False
