from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apeiria.db.base import Base, TimestampMixin, _epoch_ms


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_session"
    __table_args__ = (
        CheckConstraint(
            "scene_type IN ('group', 'private')", name="ck_chat_session_scene_type"
        ),
        UniqueConstraint(
            "platform",
            "bot_id",
            "scene_type",
            "scene_id",
            name="uq_chat_session_identity",
        ),
        Index("idx_chat_session_last_message_at", "last_message_at"),
    )

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    bot_id: Mapped[str] = mapped_column(Text, nullable=False)
    scene_type: Mapped[str] = mapped_column(Text, nullable=False)
    scene_id: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    extra_json: Mapped[str | None] = mapped_column(Text)
    last_message_at: Mapped[int] = mapped_column(Integer, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"
    __table_args__ = (
        CheckConstraint(
            "author_role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_chat_message_author_role",
        ),
        CheckConstraint(
            "message_kind IN ('text', 'mixed', 'media', 'system', 'tool')",
            name="ck_chat_message_message_kind",
        ),
        CheckConstraint(
            "turn_disposition IN ('active', 'pruned', 'summarized', 'archived')",
            name="ck_chat_message_turn_disposition",
        ),
        CheckConstraint(
            "directed_to_bot IN (0, 1)", name="ck_chat_message_directed_to_bot"
        ),
        CheckConstraint("mentions_bot IN (0, 1)", name="ck_chat_message_mentions_bot"),
        CheckConstraint("has_media IN (0, 1)", name="ck_chat_message_has_media"),
        Index("idx_chat_message_session_created", "session_id", "created_at"),
        Index("idx_chat_message_platform_message_id", "platform_message_id"),
        Index("idx_chat_message_created_at", "created_at"),
    )

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chat_session.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_message_id: Mapped[str | None] = mapped_column(Text)
    reply_to_message_id: Mapped[str | None] = mapped_column(Text)
    platform_reply_id: Mapped[str | None] = mapped_column(Text)
    author_role: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str | None] = mapped_column(Text)
    message_kind: Mapped[str] = mapped_column(Text, nullable=False)
    turn_disposition: Mapped[str] = mapped_column(
        Text, nullable=False, default="active"
    )
    directed_to_bot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mentions_bot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_media: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=_epoch_ms)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class ChatSessionContextSummary(Base):
    __tablename__ = "chat_session_context_summary"
    __table_args__ = (
        CheckConstraint("length(summary_text) > 0", name="ck_context_summary_nonempty"),
    )

    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chat_session.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_until_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_until_created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(
        Integer, nullable=False, default=_epoch_ms, onupdate=_epoch_ms
    )
