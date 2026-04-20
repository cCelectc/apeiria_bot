"""ChatSession model — generic persisted chat session boundary."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class ChatSession(Model):
    """Canonical persisted chat session for one platform/bot/scene boundary."""

    __tablename__ = "chat_session"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "bot_id",
            "scene_type",
            "scene_id",
            name="uq_chat_session_scene",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    bot_id: Mapped[str] = mapped_column(String(64), index=True)
    scene_type: Mapped[str] = mapped_column(String(16), index=True)
    scene_id: Mapped[str] = mapped_column(String(128), index=True)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
    last_message_at: Mapped[datetime] = mapped_column(insert_default=func.now())
