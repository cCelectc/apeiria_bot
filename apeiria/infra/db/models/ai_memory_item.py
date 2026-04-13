"""AIMemoryItem model — structured long-term memory storage."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AIMemoryItem(Model):
    """One structured AI memory item."""

    __tablename__ = "ai_memory_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    memory_domain: Mapped[str] = mapped_column(String(32), index=True, default="social")
    memory_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text)
    source_turn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salience: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_recalled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
