from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _epoch_ms


class AIRuntimeSettings(Base):
    __tablename__ = "ai_runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allow_group_initiative: Mapped[int | None] = mapped_column(Integer)
    quiet_hours_enabled: Mapped[int | None] = mapped_column(Integer)
    quiet_hours_start_minute: Mapped[int | None] = mapped_column(Integer)
    quiet_hours_end_minute: Mapped[int | None] = mapped_column(Integer)
    night_awake_lease_minutes: Mapped[int | None] = mapped_column(Integer)
    stt_input_enabled: Mapped[int | None] = mapped_column(Integer)
    persist_raw_event_payloads: Mapped[int | None] = mapped_column(Integer)
    ambient_merge_window_ms: Mapped[int | None] = mapped_column(Integer)
    max_pending_messages: Mapped[int | None] = mapped_column(Integer)
    group_reply_cooldown_seconds: Mapped[int | None] = mapped_column(Integer)
    max_consecutive_ambient_replies: Mapped[int | None] = mapped_column(Integer)
    direct_bypass_ambient_budget: Mapped[int | None] = mapped_column(Integer)
    duplicate_event_ttl_seconds: Mapped[int | None] = mapped_column(Integer)
    tool_execution_timeout_seconds: Mapped[float | None] = mapped_column(Float)
    cleanup_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    conversation_retention_days: Mapped[int | None] = mapped_column(Integer)
    raw_event_retention_days: Mapped[int | None] = mapped_column(Integer)
    tool_execution_retention_days: Mapped[int | None] = mapped_column(Integer)
    suppressed_memory_retention_days: Mapped[int | None] = mapped_column(Integer)
    relationship_event_retention_days: Mapped[int | None] = mapped_column(Integer)
    future_task_retention_days: Mapped[int | None] = mapped_column(Integer)
    trace_enabled: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ai_runtime_settings_singleton"),
        CheckConstraint(
            "allow_group_initiative IS NULL OR allow_group_initiative IN (0, 1)",
            name="ck_ai_runtime_settings_allow_group_initiative",
        ),
        CheckConstraint(
            "quiet_hours_enabled IS NULL OR quiet_hours_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_quiet_hours_enabled",
        ),
        CheckConstraint(
            "quiet_hours_start_minute IS NULL OR "
            "(quiet_hours_start_minute >= 0 AND quiet_hours_start_minute <= 1439)",
            name="ck_ai_runtime_settings_quiet_hours_start_minute",
        ),
        CheckConstraint(
            "quiet_hours_end_minute IS NULL OR "
            "(quiet_hours_end_minute >= 0 AND quiet_hours_end_minute <= 1439)",
            name="ck_ai_runtime_settings_quiet_hours_end_minute",
        ),
        CheckConstraint(
            "night_awake_lease_minutes IS NULL OR "
            "(night_awake_lease_minutes >= 1 AND night_awake_lease_minutes <= 120)",
            name="ck_ai_runtime_settings_night_awake_lease_minutes",
        ),
        CheckConstraint(
            "stt_input_enabled IS NULL OR stt_input_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_stt_input_enabled",
        ),
        CheckConstraint(
            "persist_raw_event_payloads IS NULL "
            "OR persist_raw_event_payloads IN (0, 1)",
            name="ck_ai_runtime_settings_persist_raw_event_payloads",
        ),
        CheckConstraint(
            "ambient_merge_window_ms IS NULL OR ambient_merge_window_ms >= 0",
            name="ck_ai_runtime_settings_ambient_merge_window_ms",
        ),
        CheckConstraint(
            "max_pending_messages IS NULL OR max_pending_messages >= 1",
            name="ck_ai_runtime_settings_max_pending_messages",
        ),
        CheckConstraint(
            "group_reply_cooldown_seconds IS NULL OR group_reply_cooldown_seconds >= 0",
            name="ck_ai_runtime_settings_group_reply_cooldown_seconds",
        ),
        CheckConstraint(
            "max_consecutive_ambient_replies IS NULL "
            "OR max_consecutive_ambient_replies >= 0",
            name="ck_ai_runtime_settings_max_consecutive_ambient_replies",
        ),
        CheckConstraint(
            "direct_bypass_ambient_budget IS NULL "
            "OR direct_bypass_ambient_budget IN (0, 1)",
            name="ck_ai_runtime_settings_direct_bypass_ambient_budget",
        ),
        CheckConstraint(
            "duplicate_event_ttl_seconds IS NULL OR duplicate_event_ttl_seconds >= 1",
            name="ck_ai_runtime_settings_duplicate_event_ttl_seconds",
        ),
        CheckConstraint(
            "tool_execution_timeout_seconds IS NULL "
            "OR tool_execution_timeout_seconds > 0",
            name="ck_ai_runtime_settings_tool_execution_timeout_seconds",
        ),
        CheckConstraint(
            "cleanup_interval_minutes IS NULL OR cleanup_interval_minutes >= 1",
            name="ck_ai_runtime_settings_cleanup_interval_minutes",
        ),
        CheckConstraint(
            "conversation_retention_days IS NULL OR conversation_retention_days >= 1",
            name="ck_ai_runtime_settings_conversation_retention_days",
        ),
        CheckConstraint(
            "raw_event_retention_days IS NULL OR raw_event_retention_days >= 1",
            name="ck_ai_runtime_settings_raw_event_retention_days",
        ),
        CheckConstraint(
            "tool_execution_retention_days IS NULL "
            "OR tool_execution_retention_days >= 1",
            name="ck_ai_runtime_settings_tool_execution_retention_days",
        ),
        CheckConstraint(
            "suppressed_memory_retention_days IS NULL "
            "OR suppressed_memory_retention_days >= 1",
            name="ck_ai_runtime_settings_suppressed_memory_retention_days",
        ),
        CheckConstraint(
            "relationship_event_retention_days IS NULL "
            "OR relationship_event_retention_days >= 1",
            name="ck_ai_runtime_settings_relationship_event_retention_days",
        ),
        CheckConstraint(
            "future_task_retention_days IS NULL OR future_task_retention_days >= 1",
            name="ck_ai_runtime_settings_future_task_retention_days",
        ),
        CheckConstraint(
            "trace_enabled IS NULL OR trace_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_trace_enabled",
        ),
    )
