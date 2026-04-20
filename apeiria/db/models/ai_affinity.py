"""AIAffinity model — structured relationship state for one user in one scene."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class AIAffinity(Model):
    """Persisted relationship state for one platform/group/user tuple."""

    __tablename__ = "ai_affinity"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "scope_key",
            "user_id",
            name="uq_ai_affinity_scope_key_subject",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    affinity_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    group_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    scope_key: Mapped[str] = mapped_column(String(160), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    mood_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    last_event_at: Mapped[datetime] = mapped_column()
    last_decay_at: Mapped[datetime | None] = mapped_column(nullable=True)
