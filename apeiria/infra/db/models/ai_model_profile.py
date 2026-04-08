"""AIModelProfile model — persisted model routing profiles."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AIModelProfile(Model):
    """One persisted model profile."""

    __tablename__ = "ai_model_profile"
    __table_args__ = (
        UniqueConstraint(
            "task_class",
            "priority",
            name="uq_ai_model_profile_task_priority",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    model_name: Mapped[str] = mapped_column(String(128))
    task_class: Mapped[str] = mapped_column(String(64), index=True)
    priority: Mapped[int] = mapped_column(default=100)
    enabled: Mapped[bool] = mapped_column(default=True)
    fallback_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
