"""Admin-only AI workbench view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition


@dataclass(frozen=True)
class AIRecentTarget:
    """Owner-facing recent target for browsing AI state."""

    target_type: str
    subject_type: str
    subject_id: str
    title: str
    subtitle: str | None
    conversation_id: str | None
    platform: str | None
    scope_type: str | None
    scope_id: str | None
    subject_user_id: str | None
    last_active_at: str | None


@dataclass(frozen=True)
class AIConversationPromptPreview:
    """Workbench prompt/context preview for one conversation."""

    conversation_id: str
    latest_user_message: str | None
    planning_source_id: str | None
    planning_profile_id: str | None
    planning_model_name: str | None
    planning_task_class: str | None
    roleplay_source_id: str | None
    roleplay_profile_id: str | None
    roleplay_model_name: str | None
    roleplay_task_class: str | None
    source_id: str | None
    profile_id: str | None
    model_name: str | None
    persona_id: str | None
    conversation_summary: str | None
    relationship_context: str | None
    tool_policy: str | None
    social_action: str | None
    social_tool_mode: str | None
    social_reason_text: str | None
    social_reason_codes: tuple[str, ...]
    social_policy_source: str | None
    tool_results: tuple[str, ...]
    memories: tuple[AIMemoryDefinition, ...]
    social_memory_count: int
    knowledge_memory_count: int
    rendered_roleplay_prompt: str | None
    rendered_prompt: str
