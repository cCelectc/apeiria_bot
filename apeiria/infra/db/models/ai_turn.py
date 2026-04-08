"""AITurn model — persisted conversation turns for the AI context kernel."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AITurn(Model):
    """One persisted AI conversation turn."""

    __tablename__ = "ai_turn"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    turn_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    conversation_pk: Mapped[int] = mapped_column(
        ForeignKey("ai_conversation.id", ondelete="CASCADE"),
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(String(16), index=True)
    sender_id: Mapped[str] = mapped_column(String(64), index=True)
    content_text: Mapped[str] = mapped_column(Text)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
