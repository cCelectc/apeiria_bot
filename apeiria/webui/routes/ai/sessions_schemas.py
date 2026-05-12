"""Schema models for AI session-read routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .memories_schemas import AIMemoryItem, to_ai_memory_item

if TYPE_CHECKING:
    from apeiria.app.ai.sessions.models import (
        AIRecentTarget,
        AISessionDetail,
        AISessionDetailMessage,
        AISessionInventoryItem,
        AISessionPersonaSummary,
        AISessionPromptChannels,
        AISessionPromptDiagnostics,
        AISessionPromptPreview,
        AISessionPromptSection,
        AISessionTraceEntry,
    )
    from apeiria.conversation.models import ChatMessageDetailView, ChatSessionAdminView


class AIRecentTargetItem(BaseModel):
    target_type: str
    anchor_type: str
    anchor_id: str
    title: str
    subtitle: str | None = None
    scene_id: str | None = None
    platform: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    user_id: str | None = None
    last_active_at: str | None = None


class AISessionItem(BaseModel):
    session_id: str
    platform: str
    bot_id: str
    scene_type: str
    scene_id: str
    subject_id: str | None = None
    summary_text: str | None = None
    created_at: str
    updated_at: str
    last_message_at: str


class AIManagedSessionPersonaItem(BaseModel):
    persona_id: str
    name: str
    enabled: bool


class AIManagedSessionItem(BaseModel):
    session_id: str
    platform_id: str
    platform_type: str
    message_type: str
    subject_id: str
    source_labels: dict[str, str] = Field(default_factory=dict)
    ai_enabled: bool
    persona: AIManagedSessionPersonaItem | None = None
    last_observed_at: str | None = None
    last_message_at: str | None = None
    message_count: int = 0
    diagnostic_count: int = 0


class AIManagedSessionMessageItem(BaseModel):
    message_id: str
    author_role: str
    author_id: str
    text_content: str
    created_at: str
    before_reset_boundary: bool
    trace_id: str | None = None
    model_name: str | None = None


class AIManagedSessionTraceItem(BaseModel):
    trace_id: str
    terminal_status: str
    skip_reason: str | None = None
    created_at: str


class AIManagedSessionDetailItem(BaseModel):
    session_id: str
    platform_id: str
    platform_type: str
    message_type: str
    subject_id: str
    source_labels: dict[str, str] = Field(default_factory=dict)
    ai_enabled: bool
    persona: AIManagedSessionPersonaItem | None = None
    recent_messages: list[AIManagedSessionMessageItem] = Field(default_factory=list)
    reset_boundary_at: str | None = None
    prompt_preview_session_id: str
    trace_entries: list[AIManagedSessionTraceItem] = Field(default_factory=list)
    model_summary: dict[str, str | None] = Field(default_factory=dict)
    strategy_summary: dict[str, str | None] = Field(default_factory=dict)
    tool_summary: dict[str, int] = Field(default_factory=dict)
    diagnostics: dict[str, str | None] = Field(default_factory=dict)


class AIManagedSessionAIEnabledUpdate(BaseModel):
    ai_enabled: bool


class AIManagedSessionPersonaUpdate(BaseModel):
    persona_id: str | None = None


class AIChatMessageItem(BaseModel):
    message_id: str
    session_id: str
    author_role: str
    author_id: str
    author_name: str | None = None
    turn_disposition: str = "active"
    text_content: str
    content: dict[str, object] | None = None
    meta: dict[str, object] | None = None
    raw_data: dict[str, object] | None = None
    created_at: str
    trace_id: str | None = None
    source_id: str | None = None
    model_name: str | None = None
    recalled_memory_count: int | None = None
    tool_observation_count: int | None = None


class AISessionPromptChannelsItem(BaseModel):
    mode: str
    system_instructions: list[str] = []
    persona: str
    style: str | None = None
    relationship: str | None = None
    person_profile: list[str] = []
    social_policy: str | None = None
    tool_policy: str | None = None
    future_task: str | None = None
    tool_results: list[str] = []
    operator_memories: list[str] = []
    summary_memories: list[str] = []
    long_term_memories: list[str] = []
    knowledge_memories: list[str] = []
    conversation_summary: str | None = None
    context_priority: list[str] = []
    conversation_messages: list[str] = []
    response_rules: list[str] = []
    instruction: str
    sections: list["AISessionPromptSectionItem"] = []


class AISessionPromptDiagnosticsItem(BaseModel):
    prompt_purpose: str
    stable_section_names: list[str] = Field(default_factory=list)
    dynamic_section_names: list[str] = Field(default_factory=list)
    stable_section_count: int = 0
    dynamic_section_count: int = 0
    total_section_count: int = 0


class AISessionPromptSectionItem(BaseModel):
    role: str
    name: str
    content: str


class AISessionPromptPreviewItem(BaseModel):
    session_id: str
    latest_user_message: str | None = None
    planning_source_id: str | None = None
    planning_profile_id: str | None = None
    planning_model_name: str | None = None
    planning_task_class: str | None = None
    roleplay_source_id: str | None = None
    roleplay_profile_id: str | None = None
    roleplay_model_name: str | None = None
    roleplay_task_class: str | None = None
    source_id: str | None = None
    profile_id: str | None = None
    model_name: str | None = None
    persona_id: str | None = None
    conversation_summary: str | None = None
    relationship_context: str | None = None
    tool_policy: str | None = None
    hard_rule_action: str | None = None
    hard_rule_reason_text: str | None = None
    hard_rule_reason_codes: list[str] = []
    social_action: str | None = None
    social_tool_mode: str | None = None
    social_reason_text: str | None = None
    social_reason_codes: list[str] = []
    social_policy_source: str | None = None
    preview_diagnostics: list[str] = []
    tool_results: list[str] = []
    memories: list[AIMemoryItem] = []
    operator_memory_count: int = 0
    summary_memory_count: int = 0
    long_term_memory_count: int = 0
    knowledge_memory_count: int = 0
    planning_prompt_diagnostics: AISessionPromptDiagnosticsItem
    roleplay_prompt_diagnostics: AISessionPromptDiagnosticsItem | None = None
    planning_channels: AISessionPromptChannelsItem
    roleplay_channels: AISessionPromptChannelsItem | None = None
    rendered_roleplay_prompt: str | None = None
    rendered_prompt: str


def to_ai_recent_target_item(item: "AIRecentTarget") -> AIRecentTargetItem:
    return AIRecentTargetItem(
        target_type=item.target_type,
        anchor_type=item.anchor_type,
        anchor_id=item.anchor_id,
        title=item.title,
        subtitle=item.subtitle,
        scene_id=item.scene_id,
        platform=item.platform,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        user_id=item.user_id,
        last_active_at=item.last_active_at,
    )


def to_ai_session_item(item: "ChatSessionAdminView") -> AISessionItem:
    return AISessionItem(
        session_id=item.session_id,
        platform=item.platform,
        bot_id=item.bot_id,
        scene_type=item.scene_type,
        scene_id=item.scene_id,
        subject_id=item.subject_id,
        summary_text=item.summary_text,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
        last_message_at=item.last_message_at.isoformat(),
    )


def to_ai_managed_session_persona_item(
    item: "AISessionPersonaSummary",
) -> AIManagedSessionPersonaItem:
    return AIManagedSessionPersonaItem(
        persona_id=item.persona_id,
        name=item.name,
        enabled=item.enabled,
    )


def to_ai_managed_session_item(
    item: "AISessionInventoryItem",
) -> AIManagedSessionItem:
    identity = item.source_identity.identity
    return AIManagedSessionItem(
        session_id=item.session_id,
        platform_id=identity.platform_id,
        platform_type=identity.platform_type,
        message_type=identity.message_type,
        subject_id=identity.subject_id,
        source_labels=item.source_labels,
        ai_enabled=item.ai_enabled,
        persona=(
            to_ai_managed_session_persona_item(item.persona)
            if item.persona is not None
            else None
        ),
        last_observed_at=(
            item.last_observed_at.isoformat()
            if item.last_observed_at is not None
            else None
        ),
        last_message_at=(
            item.last_message_at.isoformat()
            if item.last_message_at is not None
            else None
        ),
        message_count=item.message_count,
        diagnostic_count=item.diagnostic_count,
    )


def to_ai_managed_session_message_item(
    item: "AISessionDetailMessage",
) -> AIManagedSessionMessageItem:
    return AIManagedSessionMessageItem(
        message_id=item.message_id,
        author_role=item.author_role,
        author_id=item.author_id,
        text_content=item.text_content,
        created_at=item.created_at.isoformat(),
        before_reset_boundary=item.before_reset_boundary,
        trace_id=item.trace_id,
        model_name=item.model_name,
    )


def to_ai_managed_session_trace_item(
    item: "AISessionTraceEntry",
) -> AIManagedSessionTraceItem:
    return AIManagedSessionTraceItem(
        trace_id=item.trace_id,
        terminal_status=item.terminal_status,
        skip_reason=item.skip_reason,
        created_at=item.created_at.isoformat(),
    )


def to_ai_managed_session_detail_item(
    item: "AISessionDetail",
) -> AIManagedSessionDetailItem:
    identity = item.source_identity.identity
    return AIManagedSessionDetailItem(
        session_id=item.session_id,
        platform_id=identity.platform_id,
        platform_type=identity.platform_type,
        message_type=identity.message_type,
        subject_id=identity.subject_id,
        source_labels=item.source_identity.source_labels,
        ai_enabled=item.ai_enabled,
        persona=(
            to_ai_managed_session_persona_item(item.persona)
            if item.persona is not None
            else None
        ),
        recent_messages=[
            to_ai_managed_session_message_item(message)
            for message in item.recent_messages
        ],
        reset_boundary_at=(
            item.reset_boundary_at.isoformat()
            if item.reset_boundary_at is not None
            else None
        ),
        prompt_preview_session_id=item.prompt_preview_entry.session_id,
        trace_entries=[
            to_ai_managed_session_trace_item(trace) for trace in item.trace_entries
        ],
        model_summary=item.model_summary,
        strategy_summary=item.strategy_summary,
        tool_summary=item.tool_summary,
        diagnostics=item.diagnostics,
    )


def to_ai_chat_message_item(item: "ChatMessageDetailView") -> AIChatMessageItem:
    return AIChatMessageItem(
        message_id=item.message_id,
        session_id=item.session_id,
        author_role=item.author_role,
        author_id=item.author_id,
        author_name=item.author_name,
        turn_disposition=item.turn_disposition,
        text_content=item.text_content,
        content=item.content,
        meta=item.meta,
        raw_data=item.raw_data,
        created_at=item.created_at.isoformat(),
        trace_id=item.trace_id,
        source_id=item.source_id,
        model_name=item.model_name,
        recalled_memory_count=item.recalled_memory_count,
        tool_observation_count=item.tool_observation_count,
    )


def to_ai_session_prompt_section_item(
    item: "AISessionPromptSection",
) -> AISessionPromptSectionItem:
    return AISessionPromptSectionItem(
        role=item.role,
        name=item.name,
        content=item.content,
    )


def to_ai_session_prompt_diagnostics_item(
    item: "AISessionPromptDiagnostics",
) -> AISessionPromptDiagnosticsItem:
    return AISessionPromptDiagnosticsItem(
        prompt_purpose=item.prompt_purpose,
        stable_section_names=list(item.stable_section_names),
        dynamic_section_names=list(item.dynamic_section_names),
        stable_section_count=item.stable_section_count,
        dynamic_section_count=item.dynamic_section_count,
        total_section_count=item.total_section_count,
    )


def to_ai_session_prompt_channels_item(
    item: "AISessionPromptChannels",
) -> AISessionPromptChannelsItem:
    return AISessionPromptChannelsItem(
        mode=item.mode,
        system_instructions=list(item.system_instructions),
        persona=item.persona,
        style=item.style,
        relationship=item.relationship,
        person_profile=list(item.person_profile),
        social_policy=item.social_policy,
        tool_policy=item.tool_policy,
        future_task=item.future_task,
        tool_results=list(item.tool_results),
        operator_memories=list(item.operator_memories),
        summary_memories=list(item.summary_memories),
        long_term_memories=list(item.long_term_memories),
        knowledge_memories=list(item.knowledge_memories),
        conversation_summary=item.conversation_summary,
        context_priority=list(item.context_priority),
        conversation_messages=list(item.conversation_messages),
        response_rules=list(item.response_rules),
        instruction=item.instruction,
        sections=[
            to_ai_session_prompt_section_item(section) for section in item.sections
        ],
    )


def to_ai_session_prompt_preview_item(
    item: "AISessionPromptPreview",
) -> AISessionPromptPreviewItem:
    return AISessionPromptPreviewItem(
        session_id=item.session_id,
        latest_user_message=item.latest_user_message,
        planning_source_id=item.planning_source_id,
        planning_profile_id=item.planning_profile_id,
        planning_model_name=item.planning_model_name,
        planning_task_class=item.planning_task_class,
        roleplay_source_id=item.roleplay_source_id,
        roleplay_profile_id=item.roleplay_profile_id,
        roleplay_model_name=item.roleplay_model_name,
        roleplay_task_class=item.roleplay_task_class,
        source_id=item.source_id,
        profile_id=item.profile_id,
        model_name=item.model_name,
        persona_id=item.persona_id,
        conversation_summary=item.conversation_summary,
        relationship_context=item.relationship_context,
        tool_policy=item.tool_policy,
        hard_rule_action=item.hard_rule_action,
        hard_rule_reason_text=item.hard_rule_reason_text,
        hard_rule_reason_codes=list(item.hard_rule_reason_codes),
        social_action=item.social_action,
        social_tool_mode=item.social_tool_mode,
        social_reason_text=item.social_reason_text,
        social_reason_codes=list(item.social_reason_codes),
        social_policy_source=item.social_policy_source,
        preview_diagnostics=list(item.preview_diagnostics),
        tool_results=list(item.tool_results),
        memories=[to_ai_memory_item(memory) for memory in item.memories],
        operator_memory_count=item.operator_memory_count,
        summary_memory_count=item.summary_memory_count,
        long_term_memory_count=item.long_term_memory_count,
        knowledge_memory_count=item.knowledge_memory_count,
        planning_prompt_diagnostics=to_ai_session_prompt_diagnostics_item(
            item.planning_prompt_diagnostics,
        ),
        roleplay_prompt_diagnostics=(
            to_ai_session_prompt_diagnostics_item(item.roleplay_prompt_diagnostics)
            if item.roleplay_prompt_diagnostics is not None
            else None
        ),
        planning_channels=to_ai_session_prompt_channels_item(item.planning_channels),
        roleplay_channels=(
            to_ai_session_prompt_channels_item(item.roleplay_channels)
            if item.roleplay_channels is not None
            else None
        ),
        rendered_roleplay_prompt=item.rendered_roleplay_prompt,
        rendered_prompt=item.rendered_prompt,
    )
