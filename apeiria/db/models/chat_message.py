"""ChatMessage model — generic persisted message for chat session history."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class ChatMessage(Model):
    """One persisted normalized message within a chat session."""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_pk: Mapped[int] = mapped_column(
        ForeignKey("chat_session.id", ondelete="CASCADE"),
        index=True,
    )
    platform_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reply_to_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_reply_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    author_role: Mapped[str] = mapped_column(String(16), index=True)
    author_id: Mapped[str] = mapped_column(String(64), index=True)
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message_kind: Mapped[str] = mapped_column(String(16), index=True)
    directed_to_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    mentions_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    text_content: Mapped[str] = mapped_column(Text)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
