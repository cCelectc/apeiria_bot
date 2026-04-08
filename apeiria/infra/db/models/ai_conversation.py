"""AIConversation model — canonical AI scene identity and short summary."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AIConversation(Model):
    """Canonical AI conversation row for one platform/bot/scope boundary."""

    __tablename__ = "ai_conversation"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "bot_id",
            "scope_type",
            "scope_id",
            name="uq_ai_conversation_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    bot_id: Mapped[str] = mapped_column(String(64), index=True)
    scope_type: Mapped[str] = mapped_column(String(16), index=True)
    scope_id: Mapped[str] = mapped_column(String(128), index=True)
    subject_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    short_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
    last_active_at: Mapped[datetime] = mapped_column(insert_default=func.now())
