from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, TimestampMixin, _epoch_ms


class AIManagedSession(TimestampMixin, Base):
    __tablename__ = "ai_managed_session"
    __table_args__ = (
        CheckConstraint(
            "message_type IN ('group', 'private', 'web_chat')",
            name="ck_ai_managed_session_message_type",
        ),
        CheckConstraint(
            "ai_enabled IN (0, 1)", name="ck_ai_managed_session_ai_enabled"
        ),
        UniqueConstraint(
            "platform_id",
            "platform_type",
            "message_type",
            "subject_id",
            name="uq_ai_managed_session_identity",
        ),
        Index(
            "idx_ai_managed_session_source",
            "platform_id",
            "platform_type",
            "message_type",
            "subject_id",
        ),
        Index("idx_ai_managed_session_recent", "last_observed_at", "updated_at"),
    )

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform_id: Mapped[str] = mapped_column(Text, nullable=False)
    platform_type: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_labels_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    diagnostic_raw_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    ai_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    persona_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("ai_persona.persona_id", ondelete="SET NULL")
    )
    context_reset_at: Mapped[int | None] = mapped_column(Integer)
    context_reset_by: Mapped[str | None] = mapped_column(Text)
    last_observed_at: Mapped[int | None] = mapped_column(Integer, default=_epoch_ms)
    last_user_message_at: Mapped[int | None] = mapped_column(Integer)
    last_ai_message_at: Mapped[int | None] = mapped_column(Integer)
    audit_created_by: Mapped[str | None] = mapped_column(Text)
    audit_updated_by: Mapped[str | None] = mapped_column(Text)
