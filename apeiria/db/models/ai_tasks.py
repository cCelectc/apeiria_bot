from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, TimestampMixin


class AIFutureTask(TimestampMixin, Base):
    __tablename__ = "ai_future_task"

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("chat_session.session_id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(Text)
    scene_type: Mapped[str] = mapped_column(Text)
    scene_id: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    trigger_at: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[str | None] = mapped_column(Text)
    scheduler_job_id: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    claimed_at: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[int | None] = mapped_column(Integer)
    recovery_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "scene_type IN ('group', 'private')", name="ck_ai_future_task_scene_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'sent', 'cancelled', 'failed')",
            name="ck_ai_future_task_status",
        ),
        CheckConstraint("claim_count >= 0", name="ck_ai_future_task_claim_count"),
        Index("ix_ai_future_task_session", "session_id"),
        Index("ix_ai_future_task_status_trigger", "status", "trigger_at"),
        Index("ix_ai_future_task_updated_at", "updated_at"),
    )


class AIDeliveryAttempt(TimestampMixin, Base):
    __tablename__ = "ai_delivery_attempt"

    attempt_id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_future_task.task_id", ondelete="CASCADE")
    )
    trace_id: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text)
    delivery_intent: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text)
    scene_type: Mapped[str] = mapped_column(Text)
    scene_id: Mapped[str] = mapped_column(Text)
    message_preview: Mapped[str] = mapped_column(Text)
    message_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    diagnostics_json: Mapped[str] = mapped_column(Text, default="{}")
    channel: Mapped[str | None] = mapped_column(Text)
    remote_message_id: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_at: Mapped[int | None] = mapped_column(Integer)
    failed_at: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "scene_type IN ('group', 'private')",
            name="ck_ai_delivery_attempt_scene_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="ck_ai_delivery_attempt_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_ai_delivery_attempt_attempt_count",
        ),
        Index(
            "ix_ai_delivery_attempt_task_intent",
            "task_id",
            "delivery_intent",
            "status",
        ),
        Index(
            "ix_ai_delivery_attempt_pending",
            "task_id",
            "delivery_intent",
            sqlite_where=text("status = 'pending'"),
            unique=True,
        ),
        Index(
            "ix_ai_delivery_attempt_delivered",
            "task_id",
            "delivery_intent",
            sqlite_where=text("status = 'delivered'"),
            unique=True,
        ),
        Index("ix_ai_delivery_attempt_updated_at", "updated_at"),
    )
