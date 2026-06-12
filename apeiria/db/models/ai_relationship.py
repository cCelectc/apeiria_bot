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

from apeiria.db.base import Base, TimestampMixin


class AIProfile(TimestampMixin, Base):
    __tablename__ = "ai_profile"

    profile_id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    preferred_name: Mapped[str | None] = mapped_column(Text)
    name_source: Mapped[str | None] = mapped_column(Text)
    name_visibility: Mapped[str] = mapped_column(Text, default="public_allowed")
    profile_enabled: Mapped[int] = mapped_column(Integer, default=1)
    last_interaction_at: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "name_source IS NULL OR name_source IN "
            "('manual', 'self_introduced', 'platform', 'inferred')",
            name="ck_ai_profile_name_source",
        ),
        CheckConstraint(
            "name_visibility IN ('private_only', 'public_allowed', 'disabled')",
            name="ck_ai_profile_name_visibility",
        ),
        CheckConstraint(
            "profile_enabled IN (0, 1)", name="ck_ai_profile_profile_enabled"
        ),
        UniqueConstraint("platform", "user_id", name="uq_ai_profile_platform_user"),
        Index("ix_ai_profile_last_interaction", "last_interaction_at"),
    )


class AIAffinity(Base):
    __tablename__ = "ai_affinity"

    affinity_id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    mood_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    last_event_at: Mapped[int] = mapped_column(Integer)
    last_decay_at: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("score BETWEEN -100 AND 100", name="ck_ai_affinity_score"),
        UniqueConstraint("platform", "user_id", name="uq_ai_affinity_platform_user"),
        Index("ix_ai_affinity_user", "platform", "user_id"),
    )


class AIRelationshipEvent(Base):
    __tablename__ = "ai_relationship_event"

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    affinity_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_affinity.affinity_id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text)
    scene_id: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    score_delta: Mapped[int] = mapped_column(Integer)
    score_after: Mapped[int] = mapped_column(Integer)
    mood_tag: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('message', 'manual', 'decay')",
            name="ck_ai_relationship_event_event_type",
        ),
        CheckConstraint(
            "score_after BETWEEN -100 AND 100",
            name="ck_ai_relationship_event_score_after",
        ),
        Index("ix_ai_relationship_event_affinity", "affinity_id"),
        Index("ix_ai_relationship_event_created_at", "created_at"),
    )
