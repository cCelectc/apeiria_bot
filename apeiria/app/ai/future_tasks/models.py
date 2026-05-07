"""Future task domain models for proactive AI reminders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.conversation.models import SceneType

AIFutureTaskStatus = Literal["pending", "running", "sent", "cancelled", "failed"]
AIFutureTaskToolAction = Literal["create", "cancel", "list"]


@dataclass(frozen=True)
class AIFutureTaskCreateInput:
    """Create payload for one persisted AI future task."""

    session_id: str
    platform: str
    scene_type: SceneType
    scene_id: str
    user_id: str | None
    title: str
    description: str
    trigger_at: datetime
    source_message_id: str | None = None


@dataclass(frozen=True)
class AIFutureTaskDefinition:
    """Read model for one future task."""

    task_id: str
    session_id: str
    platform: str
    scene_type: SceneType
    scene_id: str
    user_id: str | None
    title: str
    description: str
    trigger_at: datetime
    status: AIFutureTaskStatus
    source_message_id: str | None
    scheduler_job_id: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    claim_count: int = 0
    claimed_at: datetime | None = None
    completed_at: datetime | None = None
    recovery_reason: str | None = None


@dataclass(frozen=True)
class AIFutureTaskToolInput:
    """Structured tool input for future-task management."""

    action: AIFutureTaskToolAction
    title: str | None = None
    description: str | None = None
    trigger_at: datetime | None = None
    task_id: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class AIFutureTaskToolItem:
    """Compact future-task item returned by tool execution."""

    task_id: str
    title: str
    description: str
    trigger_at: datetime
    status: AIFutureTaskStatus


@dataclass(frozen=True)
class AIFutureTaskToolOutput:
    """Structured tool output for future-task management."""

    action: AIFutureTaskToolAction
    ok: bool
    message: str
    tasks: tuple[AIFutureTaskToolItem, ...] = ()
