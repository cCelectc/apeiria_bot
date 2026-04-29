"""AI session read models for browsing and workbench preview surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition


@dataclass(frozen=True)
class AIRecentTarget:
    """Owner-facing recent target for browsing AI state."""

    target_type: str
    anchor_type: str
    anchor_id: str
    title: str
    subtitle: str | None
    scene_id: str | None
    platform: str | None
    scope_type: str | None
    scope_id: str | None
    user_id: str | None
    last_active_at: str | None


@dataclass(frozen=True)
class AISessionPromptSection:
    """One packet-derived prompt section exposed to preview surfaces."""

    role: str
    name: str
    content: str


@dataclass(frozen=True)
class AISessionPromptDiagnostics:
    """Bounded region metadata for one composed runtime prompt."""

    prompt_purpose: str
    stable_section_names: tuple[str, ...]
    dynamic_section_names: tuple[str, ...]
    stable_section_count: int
    dynamic_section_count: int
    total_section_count: int


@dataclass(frozen=True)
class AISessionPromptChannels:
    """Structured prompt channels for one composed runtime prompt."""

    mode: str
    system_instructions: tuple[str, ...]
    persona: str
    style: str | None
    relationship: str | None
    person_profile: tuple[str, ...]
    social_policy: str | None
    tool_policy: str | None
    future_task: str | None
    tool_results: tuple[str, ...]
    operator_memories: tuple[str, ...]
    summary_memories: tuple[str, ...]
    long_term_memories: tuple[str, ...]
    knowledge_memories: tuple[str, ...]
    conversation_summary: str | None
    context_priority: tuple[str, ...]
    conversation_messages: tuple[str, ...]
    response_rules: tuple[str, ...]
    instruction: str
    sections: tuple[AISessionPromptSection, ...] = ()


@dataclass(frozen=True)
class AISessionPromptPreview:
    """Workbench prompt/context preview for one conversation."""

    session_id: str
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
    hard_rule_action: str | None
    hard_rule_reason_text: str | None
    hard_rule_reason_codes: tuple[str, ...]
    social_action: str | None
    social_tool_mode: str | None
    social_reason_text: str | None
    social_reason_codes: tuple[str, ...]
    social_policy_source: str | None
    preview_diagnostics: tuple[str, ...]
    tool_results: tuple[str, ...]
    memories: tuple["AIMemoryDefinition", ...]
    operator_memory_count: int
    summary_memory_count: int
    long_term_memory_count: int
    knowledge_memory_count: int
    planning_prompt_diagnostics: AISessionPromptDiagnostics
    roleplay_prompt_diagnostics: AISessionPromptDiagnostics | None
    planning_channels: AISessionPromptChannels
    roleplay_channels: AISessionPromptChannels | None
    rendered_roleplay_prompt: str | None
    rendered_prompt: str
