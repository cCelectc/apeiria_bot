from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base


class AIMemoryItem(Base):
    __tablename__ = "ai_memory_item"

    memory_id: Mapped[str] = mapped_column(Text, primary_key=True)
    anchor_type: Mapped[str] = mapped_column(Text)
    anchor_id: Mapped[str] = mapped_column(Text)
    memory_layer: Mapped[str] = mapped_column(Text)
    memory_kind: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    is_editable: Mapped[int] = mapped_column(Integer, default=1)
    lifecycle_state: Mapped[str] = mapped_column(Text, default="active")
    default_use_mode: Mapped[str] = mapped_column(Text, default="context")
    governance_reason: Mapped[str | None] = mapped_column(Text)
    source_message_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("chat_message.message_id", ondelete="SET NULL")
    )
    salience: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_recalled_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "anchor_type IN ('operator', 'scene', 'participant', 'user', 'project')",
            name="ck_ai_memory_item_anchor_type",
        ),
        CheckConstraint(
            "memory_layer IN ('summary', 'long_term', 'knowledge', 'operator')",
            name="ck_ai_memory_item_memory_layer",
        ),
        CheckConstraint(
            "memory_kind IN "
            "('fact', 'preference', 'relationship', 'note', 'impression')",
            name="ck_ai_memory_item_memory_kind",
        ),
        CheckConstraint("is_editable IN (0, 1)", name="ck_ai_memory_item_is_editable"),
        CheckConstraint(
            "lifecycle_state IN ('candidate', 'active', 'suppressed', 'archived')",
            name="ck_ai_memory_item_lifecycle_state",
        ),
        CheckConstraint(
            "default_use_mode IN ('ignore', 'silent', 'context', 'explicit')",
            name="ck_ai_memory_item_default_use_mode",
        ),
        CheckConstraint(
            "salience BETWEEN 0.0 AND 1.0", name="ck_ai_memory_item_salience"
        ),
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0", name="ck_ai_memory_item_confidence"
        ),
        UniqueConstraint(
            "anchor_type",
            "anchor_id",
            "memory_layer",
            "memory_kind",
            "content",
            name="uq_ai_memory_item_anchor_content",
        ),
        Index(
            "ix_ai_memory_item_anchor_layer_kind",
            "anchor_type",
            "anchor_id",
            "memory_layer",
            "memory_kind",
        ),
        Index("ix_ai_memory_item_lifecycle_created", "lifecycle_state", "created_at"),
    )
