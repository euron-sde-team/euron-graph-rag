from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from graphrag.db.base import Base, IdMixin, TimestampMixin


class QueryLog(IdMixin, TimestampMixin, Base):
    """A question and what answered it: the playground history and the traffic dashboard."""

    __tablename__ = "query_logs"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(String(8))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    answerer: Mapped[str] = mapped_column(String(32), default="local")
    # The full response: citations, nodes, edges and communities used, stage timings.
    result: Mapped[dict[str, Any]] = mapped_column(default=dict)
    citation_count: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cached: Mapped[bool] = mapped_column(default=False)
