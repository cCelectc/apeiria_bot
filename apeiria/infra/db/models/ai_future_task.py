"""AIFutureTask model — persisted future reminders and proactive tasks."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AIFutureTask(Model):
    """One persisted AI future task."""

    __tablename__ = "ai_future_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    conversation_id: Mapped[str] = mapped_column(String(80), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    scope_type: Mapped[str] = mapped_column(String(16), index=True)
    scope_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    trigger_at: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    source_turn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scheduler_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
