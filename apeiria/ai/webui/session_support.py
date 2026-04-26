"""Session-specific mapping helpers for AI WebUI routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.webui.schemas import (
    AIChatMessageItem,
    AIRecentTargetItem,
    AISessionItem,
    AISessionPromptChannelsItem,
    AISessionPromptPreviewItem,
)
from apeiria.ai.webui.support import to_ai_memory_item

if TYPE_CHECKING:
    from apeiria.app.ai.session_read.models import (
        AIRecentTarget,
        AISessionPromptChannels,
        AISessionPromptPreview,
    )
    from apeiria.conversation.models import (
        ChatMessageDetailView,
        ChatSessionAdminView,
    )


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


def to_ai_chat_message_item(item: "ChatMessageDetailView") -> AIChatMessageItem:
    return AIChatMessageItem(
        message_id=item.message_id,
        session_id=item.session_id,
        author_role=item.author_role,
        author_id=item.author_id,
        author_name=item.author_name,
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
        social_action=item.social_action,
        social_tool_mode=item.social_tool_mode,
        social_reason_text=item.social_reason_text,
        social_reason_codes=list(item.social_reason_codes),
        social_policy_source=item.social_policy_source,
        tool_results=list(item.tool_results),
        memories=[to_ai_memory_item(memory) for memory in item.memories],
        operator_memory_count=item.operator_memory_count,
        summary_memory_count=item.summary_memory_count,
        long_term_memory_count=item.long_term_memory_count,
        knowledge_memory_count=item.knowledge_memory_count,
        planning_channels=to_ai_session_prompt_channels_item(item.planning_channels),
        roleplay_channels=(
            to_ai_session_prompt_channels_item(item.roleplay_channels)
            if item.roleplay_channels is not None
            else None
        ),
        rendered_roleplay_prompt=item.rendered_roleplay_prompt,
        rendered_prompt=item.rendered_prompt,
    )
