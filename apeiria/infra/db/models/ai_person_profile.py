"""AIPersonProfile model — structured per-user profile storage."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Boolean, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AIPersonProfile(Model):
    """Persisted person profile for one platform and user id."""

    __tablename__ = "ai_person_profile"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "user_id",
            name="uq_ai_person_profile_platform_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    person_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_points_json: Mapped[str] = mapped_column(Text, default="[]")
    is_known: Mapped[bool] = mapped_column(Boolean, default=False)
    know_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_interaction: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
