from __future__ import annotations

from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _epoch_ms


class AIModelUsageEvent(Base):
    __tablename__ = "ai_model_usage_event"
    __table_args__ = (Index("idx_ai_model_usage_event_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=_epoch_ms)
