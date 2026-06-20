from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _epoch_ms, _now_iso


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text)
    scene_type: Mapped[str] = mapped_column(Text)
    scene_id: Mapped[str] = mapped_column(Text)
    model_override: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
    last_active_at: Mapped[str] = mapped_column(Text, default=_now_iso)
    last_compacted_message_id: Mapped[int | None] = mapped_column(Integer)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_messages_role",
        ),
        CheckConstraint(
            "type IN ('message', 'message_sent', 'system')",
            name="ck_messages_type",
        ),
        Index("idx_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, default="message")
    user_id: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(Text)
    meta_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=_epoch_ms)
