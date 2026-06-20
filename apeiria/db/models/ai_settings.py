from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _now_iso


class AIRuntimeSettings(Base):
    __tablename__ = "ai_runtime_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ai_runtime_settings_singleton"),
        CheckConstraint(
            "talk_value > 0 AND talk_value <= 1.0",
            name="ck_ai_runtime_settings_talk_value",
        ),
        CheckConstraint(
            "compaction_threshold > 0 AND compaction_threshold < 1.0",
            name="ck_ai_runtime_settings_compaction_threshold",
        ),
        CheckConstraint(
            "memory_isolate_by_session IN (0, 1)",
            name="ck_ai_runtime_settings_memory_isolate_by_session",
        ),
        CheckConstraint(
            "memory_half_life_days > 0",
            name="ck_ai_runtime_settings_memory_half_life_days",
        ),
        CheckConstraint(
            "memory_floor_ratio >= 0 AND memory_floor_ratio <= 1.0",
            name="ck_ai_runtime_settings_memory_floor_ratio",
        ),
        CheckConstraint(
            "relationship_isolate_by_session IN (0, 1)",
            name="ck_ai_runtime_settings_relationship_isolate_by_session",
        ),
        CheckConstraint(
            "relationship_half_life_days > 0",
            name="ck_ai_runtime_settings_relationship_half_life_days",
        ),
        CheckConstraint(
            "rerank_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_rerank_enabled",
        ),
        CheckConstraint(
            "segment_reply_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_segment_reply_enabled",
        ),
        CheckConstraint(
            "segment_delay_seconds >= 0",
            name="ck_ai_runtime_settings_segment_delay_seconds",
        ),
        CheckConstraint(
            "self_review_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_self_review_enabled",
        ),
        CheckConstraint(
            "acp_access_mode IN ('superuser_only', 'open')",
            name="ck_ai_runtime_settings_acp_access_mode",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    talk_value: Mapped[float] = mapped_column(Float, default=0.3)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_replies_per_window: Mapped[int] = mapped_column(Integer, default=3)
    reply_window_seconds: Mapped[int] = mapped_column(Integer, default=300)
    no_action_backoff_base_seconds: Mapped[int] = mapped_column(Integer, default=60)
    no_action_backoff_max_seconds: Mapped[int] = mapped_column(Integer, default=600)
    compaction_threshold: Mapped[float] = mapped_column(Float, default=0.8)
    memory_isolate_by_session: Mapped[int] = mapped_column(Integer, default=0)
    memory_half_life_days: Mapped[float] = mapped_column(Float, default=30.0)
    memory_floor_ratio: Mapped[float] = mapped_column(Float, default=0.1)
    relationship_isolate_by_session: Mapped[int] = mapped_column(Integer, default=0)
    relationship_half_life_days: Mapped[float] = mapped_column(Float, default=30.0)
    rerank_enabled: Mapped[int] = mapped_column(Integer, default=0)
    segment_reply_enabled: Mapped[int] = mapped_column(Integer, default=1)
    segment_delay_seconds: Mapped[float] = mapped_column(Float, default=1.5)
    self_review_enabled: Mapped[int] = mapped_column(Integer, default=0)
    default_chat_model: Mapped[str | None] = mapped_column(Text)
    reasoning_effort: Mapped[str] = mapped_column(Text, default="medium")
    acp_access_mode: Mapped[str] = mapped_column(Text, default="superuser_only")
    searxng_url: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, default=_now_iso, onupdate=_now_iso)
