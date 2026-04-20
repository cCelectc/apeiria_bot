"""AIRelationshipEvent model — persisted relationship event audit trail."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AIRelationshipEvent(Model):
    """One persisted relationship event for one affinity state."""

    __tablename__ = "ai_relationship_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    affinity_id: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    group_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    score_delta: Mapped[float] = mapped_column(Float)
    score_after: Mapped[float] = mapped_column(Float)
    mood_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
