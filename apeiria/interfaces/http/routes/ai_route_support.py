"""Pure mapping helpers for AI admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.interfaces.http.schemas.ai_models import (
    AICapabilityItem,
    AICapabilityPreviewItem,
    AIConversationItem,
    AIConversationPromptPreviewItem,
    AIConversationTurnItem,
    AIFutureTaskItem,
    AIMemoryItem,
    AIModelBindingItem,
    AIModelProfileItem,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIProviderItem,
    AIProviderModelItem,
    AIRecentTargetItem,
    AIRelationshipStateItem,
    AISkillItem,
    AIToolExecutionItem,
    AIToolIntentPreviewItem,
    AIToolItem,
    AIToolPolicyBindingItem,
    AIToolPolicyPreviewItem,
)

if TYPE_CHECKING:
    from apeiria.app.ai.admin.models import AIConversationPromptPreview, AIRecentTarget
    from apeiria.app.ai.conversation.models import (
        AIConversationAdminView,
        AIConversationTurnDetailView,
    )
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.model import (
        AIModelBindingSpec,
        AIModelProfileDefinition,
        AIProviderDefinition,
    )
    from apeiria.app.ai.model import (
        AIProviderModelItem as DomainProviderModelItem,
    )
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )
    from apeiria.app.ai.relationship.models import AIRelationshipState
    from apeiria.app.ai.skills.catalog import AISkillDefinition
    from apeiria.app.ai.tools.debug import (
        AICapabilityDefinition,
        AICapabilityPreview,
        AIToolIntentPreview,
    )
    from apeiria.app.ai.tools.models import (
        AIToolExecutionView,
        AIToolPolicy,
        AIToolSpec,
    )
    from apeiria.app.ai.tools.policy import (
        AIToolPolicyBindingSpec,
    )




def _skill_display_name(skill_name: str) -> str:
    return {
        "future_task.manage": "提醒与任务",
        "memory.query": "查询记忆",
        "plugin.capability": "调用插件能力",
        "relationship.inspect": "查看关系状态",
    }.get(skill_name, skill_name)


def _skill_display_description(skill_name: str, fallback: str) -> str:
    return {
        "future_task.manage": "创建、取消或查看机器人已安排的提醒任务。",
        "memory.query": "查看机器人为当前用户或会话召回的长期记忆内容。",
        "plugin.capability": "在允许范围内调用 NoneBot 插件能力。",
        "relationship.inspect": "查看机器人对当前用户关系状态与情绪倾向的理解。",
    }.get(skill_name, fallback)


def _skill_risk_label(risk_level: str) -> str:
    return {
        "low": "低风险",
        "medium": "中风险",
        "high": "高风险",
    }.get(risk_level, risk_level)


def to_ai_persona_item(item: "AIPersonaDefinition") -> AIPersonaItem:
    return AIPersonaItem(
        persona_id=item.persona_id,
        name=item.name,
        description=item.description,
        system_prompt=item.system_prompt,
        style_prompt=item.style_prompt,
        enabled=item.enabled,
    )


def to_ai_persona_binding_item(item: "AIPersonaBindingSpec") -> AIPersonaBindingItem:
    return AIPersonaBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        persona_id=item.persona_id,
    )


def to_ai_memory_item(item: "AIMemoryDefinition") -> AIMemoryItem:
    return AIMemoryItem(
        memory_id=item.memory_id,
        memory_type=item.memory_type,
        subject_type=item.subject_type,
        subject_id=item.subject_id,
        content=item.content,
        source_turn_id=item.source_turn_id,
        salience=item.salience,
        confidence=item.confidence,
        last_recalled_at=(
            item.last_recalled_at.isoformat() if item.last_recalled_at else None
        ),
        created_at=item.created_at.isoformat(),
    )




def to_ai_recent_target_item(item: "AIRecentTarget") -> AIRecentTargetItem:
    return AIRecentTargetItem(
        target_type=item.target_type,
        subject_type=item.subject_type,
        subject_id=item.subject_id,
        title=item.title,
        subtitle=item.subtitle,
        conversation_id=item.conversation_id,
        platform=item.platform,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        subject_user_id=item.subject_user_id,
        last_active_at=item.last_active_at,
    )

def to_ai_conversation_item(item: "AIConversationAdminView") -> AIConversationItem:
    return AIConversationItem(
        conversation_id=item.conversation_id,
        platform=item.platform,
        bot_id=item.bot_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        subject_user_id=item.subject_user_id,
        short_summary=item.short_summary,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
        last_active_at=item.last_active_at.isoformat(),
    )


def to_ai_conversation_turn_item(
    item: "AIConversationTurnDetailView",
) -> AIConversationTurnItem:
    return AIConversationTurnItem(
        turn_id=item.turn_id,
        conversation_id=item.conversation_id,
        sender_type=item.sender_type,
        sender_id=item.sender_id,
        content_text=item.content_text,
        created_at=item.created_at.isoformat(),
        raw_payload=item.raw_payload,
        trace_id=item.trace_id,
        provider_id=item.provider_id,
        model_name=item.model_name,
        recalled_memory_count=item.recalled_memory_count,
        tool_observation_count=item.tool_observation_count,
    )


def to_ai_conversation_prompt_preview_item(
    item: "AIConversationPromptPreview",
) -> AIConversationPromptPreviewItem:
    return AIConversationPromptPreviewItem(
        conversation_id=item.conversation_id,
        latest_user_message=item.latest_user_message,
        provider_id=item.provider_id,
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
        rendered_prompt=item.rendered_prompt,
    )


def to_ai_future_task_item(item: "AIFutureTaskDefinition") -> AIFutureTaskItem:
    return AIFutureTaskItem(
        task_id=item.task_id,
        conversation_id=item.conversation_id,
        platform=item.platform,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        user_id=item.user_id,
        title=item.title,
        description=item.description,
        trigger_at=item.trigger_at.isoformat(),
        status=item.status,
        source_turn_id=item.source_turn_id,
        scheduler_job_id=item.scheduler_job_id,
        last_error=item.last_error,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def to_ai_model_profile_item(item: "AIModelProfileDefinition") -> AIModelProfileItem:
    return AIModelProfileItem(
        profile_id=item.profile_id,
        name=item.name,
        provider_id=item.provider_id,
        model_name=item.model_name,
        task_class=item.task_class,
        priority=item.priority,
        enabled=item.enabled,
        fallback_profile_id=item.fallback_profile_id,
    )


def to_ai_model_binding_item(item: "AIModelBindingSpec") -> AIModelBindingItem:
    return AIModelBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        profile_id=item.profile_id,
    )


def to_ai_provider_item(item: "AIProviderDefinition") -> AIProviderItem:
    return AIProviderItem(
        provider_id=item.provider_id,
        name=item.name,
        provider_type=item.provider_type,
        api_base=item.api_base,
        api_key_env_name=item.api_key_env_name,
        enabled=item.enabled,
        default_model=item.default_model,
    )


def to_ai_provider_model_item(item: "DomainProviderModelItem") -> AIProviderModelItem:
    return AIProviderModelItem(
        id=item.id,
        name=item.name,
    )


def to_ai_relationship_state_item(
    item: "AIRelationshipState",
) -> AIRelationshipStateItem:
    return AIRelationshipStateItem(
        affinity_id=item.affinity_id,
        platform=item.platform,
        group_id=item.group_id,
        user_id=item.user_id,
        score=item.score,
        mood_tags=list(item.mood_tags),
        last_event_at=item.last_event_at.isoformat(),
    )


def to_ai_tool_item(item: "AIToolSpec") -> AIToolItem:
    return AIToolItem(
        name=item.name,
        description=item.description,
        read_only=item.read_only,
        concurrency_safe=item.concurrency_safe,
        risk_level=item.risk_level,
        is_capability_bridge=item.is_capability_bridge,
    )


def to_ai_skill_item(item: "AISkillDefinition") -> AISkillItem:
    risk_level = (
        "high"
        if item.contract.side_effect_level == "high_risk"
        else "low"
        if item.contract.side_effect_level == "read_only"
        else "medium"
    )
    return AISkillItem(
        name=item.skill_name,
        description=item.description,
        display_name=_skill_display_name(item.skill_name),
        display_description=_skill_display_description(
            item.skill_name,
            item.description,
        ),
        read_only=item.contract.side_effect_level == "read_only",
        concurrency_safe=item.contract.idempotency == "idempotent",
        risk_level=risk_level,
        risk_label=_skill_risk_label(risk_level),
        is_capability_bridge=item.skill_name == "plugin.capability",
    )


def to_ai_tool_execution_item(item: "AIToolExecutionView") -> AIToolExecutionItem:
    return AIToolExecutionItem(
        execution_id=item.execution_id,
        conversation_id=item.conversation_id,
        tool_name=item.tool_name,
        status=item.status,
        input_json=item.input_json,
        output_json=item.output_json,
        created_at=item.created_at.isoformat(),
    )


def to_ai_tool_intent_preview_item(
    item: "AIToolIntentPreview",
) -> AIToolIntentPreviewItem:
    return AIToolIntentPreviewItem(
        tool_name=item.tool_name,
        kind=item.kind,
        reason=item.reason,
        input_payload=item.input_payload,
    )


def to_ai_tool_policy_preview_item(item: "AIToolPolicy") -> AIToolPolicyPreviewItem:
    return AIToolPolicyPreviewItem(
        execution_enabled=item.execution_enabled,
        allowed_tool_names=(
            sorted(item.allowed_tool_names)
            if item.allowed_tool_names is not None
            else None
        ),
        denied_tool_names=sorted(item.denied_tool_names),
        allow_high_risk_tools=item.allow_high_risk_tools,
        allow_capability_bridge=item.allow_capability_bridge,
    )


def to_ai_tool_policy_binding_item(
    item: "AIToolPolicyBindingSpec",
) -> AIToolPolicyBindingItem:
    return AIToolPolicyBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        allow_read_only_tools=item.allow_read_only_tools,
        capability_mode=item.capability_mode,
    )


def to_ai_capability_preview_item(
    item: "AICapabilityPreview",
) -> AICapabilityPreviewItem:
    return AICapabilityPreviewItem(
        capability_name=item.capability_name,
        registered=item.registered,
        allowed=item.allowed,
        reason=item.reason,
        allow_capability_bridge=item.allow_capability_bridge,
        execution_enabled=item.execution_enabled,
    )


def to_ai_capability_item(item: "AICapabilityDefinition") -> AICapabilityItem:
    return AICapabilityItem(
        capability_name=item.capability_name,
        bound_tool_name=item.bound_tool_name,
    )
