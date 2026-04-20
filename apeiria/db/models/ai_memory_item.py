"""AIMemoryItem model — structured long-term memory storage."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Boolean, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AIMemoryItem(Model):
    """One structured AI memory item."""

    __tablename__ = "ai_memory_item"
    __table_args__ = (
        Index(
            "ix_ai_memory_item_anchor_layer_kind",
            "anchor_type",
            "anchor_id",
            "memory_layer",
            "memory_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    anchor_type: Mapped[str] = mapped_column(String(32), index=True)
    anchor_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_layer: Mapped[str] = mapped_column(String(32), index=True)
    memory_kind: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    source_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salience: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_recalled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
