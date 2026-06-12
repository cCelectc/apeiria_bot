from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base


class AIModelUsageEvent(Base):
    __tablename__ = "ai_model_usage_event"

    usage_event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    trace_id: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text)
    runtime_mode: Mapped[str] = mapped_column(Text)
    response_source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(Text)
    attempt_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    usage_available: Mapped[int] = mapped_column(Integer)
    measurement_source: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    audio_input_tokens: Mapped[int | None] = mapped_column(Integer)
    audio_output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "attempt_index >= 1",
            name="ck_ai_model_usage_event_attempt_index",
        ),
        CheckConstraint(
            "usage_available IN (0, 1)", name="ck_ai_model_usage_event_usage_available"
        ),
        CheckConstraint(
            "measurement_source IN ('provider', 'missing')",
            name="ck_ai_model_usage_event_measurement_source",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_model_usage_event_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_model_usage_event_output_tokens",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_model_usage_event_total_tokens",
        ),
        CheckConstraint(
            "cached_input_tokens IS NULL OR cached_input_tokens >= 0",
            name="ck_ai_model_usage_event_cached_input_tokens",
        ),
        CheckConstraint(
            "reasoning_tokens IS NULL OR reasoning_tokens >= 0",
            name="ck_ai_model_usage_event_reasoning_tokens",
        ),
        CheckConstraint(
            "audio_input_tokens IS NULL OR audio_input_tokens >= 0",
            name="ck_ai_model_usage_event_audio_input_tokens",
        ),
        CheckConstraint(
            "audio_output_tokens IS NULL OR audio_output_tokens >= 0",
            name="ck_ai_model_usage_event_audio_output_tokens",
        ),
        Index("ix_ai_model_usage_event_trace", "trace_id", "created_at"),
        Index("ix_ai_model_usage_event_session", "session_id", "created_at"),
        Index("ix_ai_model_usage_event_created_at", "created_at"),
    )


class AIModelUsageHourly(Base):
    __tablename__ = "ai_model_usage_hourly"

    hour_bucket: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, primary_key=True)
    operation: Mapped[str] = mapped_column(Text, primary_key=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    measured_call_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    audio_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    audio_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
