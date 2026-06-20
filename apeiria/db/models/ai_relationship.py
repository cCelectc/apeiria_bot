from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, ISOTimestampMixin, _now_iso


class RelationshipScore(Base):
    __tablename__ = "relationship_scores"
    __table_args__ = (
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_relationship_scores_score",
        ),
        Index("idx_relationship_scores_session_id", "session_id"),
    )

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=50)
    last_updated_at: Mapped[str] = mapped_column(Text, default=_now_iso)


class AIProfile(ISOTimestampMixin, Base):
    __tablename__ = "ai_profiles"
    __table_args__ = (
        UniqueConstraint("platform", "user_id", name="uq_ai_profiles_platform_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
