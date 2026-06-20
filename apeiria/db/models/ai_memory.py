from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _now_iso


class Fact(Base):
    __tablename__ = "facts"
    __table_args__ = (
        CheckConstraint(
            "embedding_status IN ('pending', 'embedded', 'failed')",
            name="ck_facts_embedding_status",
        ),
        CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_facts_importance",
        ),
        Index("idx_facts_user_id", "user_id"),
        Index("idx_facts_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    embedding_status: Mapped[str] = mapped_column(Text, default="pending")
    last_reinforced_at: Mapped[str] = mapped_column(Text, default=_now_iso)
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
