"""Pure mapping helpers for AI admin routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.ai.relationship.scoring import (
    apply_inactivity_decay,
    project_emotion,
)
from apeiria.ai.webui.schemas import (
    AICapabilityItem,
    AICapabilityPreviewItem,
    AIFutureTaskItem,
    AIMemoryItem,
    AIModelBindingItem,
    AIModelCatalogItem,
    AIModelProfileItem,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIPersonMemoryPointItem,
    AIPersonProfileItem,
    AIRelationshipEventItem,
    AIRelationshipStateItem,
    AISkillItem,
    AISourceItem,
    AISourceModelItem,
    AISourcePresetItem,
    AIToolExecutionItem,
    AIToolIntentPreviewItem,
    AIToolItem,
    AIToolPolicyBindingItem,
    AIToolPolicyPreviewItem,
)

if TYPE_CHECKING:
    from apeiria.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.ai.memory.models import AIMemoryDefinition
    from apeiria.ai.model import (
        AIModelBindingSpec,
        AIModelProfileDefinition,
        AISourceDefinition,
        AISourceModelDefinition,
        AISourcePresetDefinition,
    )
    from apeiria.ai.model import AIModelCatalogItem as DomainModelCatalogItem
    from apeiria.ai.person.models import AIPersonProfileDefinition
    from apeiria.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )
    from apeiria.ai.relationship.models import (
        AIRelationshipEvent,
        AIRelationshipState,
    )
    from apeiria.ai.skills.catalog import AISkillDefinition
    from apeiria.ai.tools.debug import (
        AICapabilityDefinition,
        AICapabilityPreview,
        AIToolIntentPreview,
    )
    from apeiria.ai.tools.models import (
        AIToolExecutionView,
        AIToolPolicy,
        AIToolSpec,
    )
    from apeiria.ai.tools.policy import (
        AIToolPolicyBindingSpec,
    )


def _skill_display_name(skill_name: str) -> str:
    return {
        "future_task.manage": "提醒与任务",
        "memory.query": "查询记忆",
        "memory.update": "修正记忆",
        "plugin.capability": "调用插件能力",
        "relationship.inspect": "查看关系状态",
    }.get(skill_name, skill_name)


def _skill_display_description(skill_name: str, fallback: str) -> str:
    return {
        "future_task.manage": "创建、取消或查看机器人已安排的提醒任务。",
        "memory.query": "查看机器人为当前用户或会话召回的长期记忆内容。",
        "memory.update": "修正当前会话中已召回的长期记忆内容。",
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
        anchor_type=item.anchor_type,
        anchor_id=item.anchor_id,
        memory_layer=item.memory_layer,
        memory_kind=item.memory_kind,
        content=item.content,
        is_editable=item.is_editable,
        is_ignored=item.is_ignored,
        source_message_id=item.source_message_id,
        salience=item.salience,
        confidence=item.confidence,
        last_recalled_at=(
            item.last_recalled_at.isoformat() if item.last_recalled_at else None
        ),
        created_at=item.created_at.isoformat(),
    )


def to_ai_source_preset_item(
    item: "AISourcePresetDefinition",
) -> AISourcePresetItem:
    return AISourcePresetItem(
        preset_type=item.preset_type,
        display_name=item.display_name,
        capability_type=item.capability_type,
        client_type=item.client_type,
        default_api_base=item.default_api_base,
        description=item.description,
    )


def to_ai_source_item(item: "AISourceDefinition") -> AISourceItem:
    return AISourceItem(
        source_id=item.source_id,
        name=item.name,
        capability_type=item.capability_type,
        client_type=item.client_type,
        preset_type=item.preset_type,
        api_base=item.api_base,
        api_key_env_name=item.api_key_env_name,
        enabled=item.enabled,
        timeout_seconds=item.timeout_seconds,
        custom_headers=item.custom_headers or {},
        extra_config=item.extra_config or {},
    )


def to_ai_source_model_item(item: "AISourceModelDefinition") -> AISourceModelItem:
    return AISourceModelItem(
        model_id=item.model_id,
        source_id=item.source_id,
        model_identifier=item.model_identifier,
        display_name=item.display_name,
        enabled=item.enabled,
        is_default=item.is_default,
        extra_params=item.extra_params or {},
    )


def to_ai_future_task_item(item: "AIFutureTaskDefinition") -> AIFutureTaskItem:
    return AIFutureTaskItem(
        task_id=item.task_id,
        session_id=item.session_id,
        platform=item.platform,
        scene_type=item.scene_type,
        scene_id=item.scene_id,
        user_id=item.user_id,
        title=item.title,
        description=item.description,
        trigger_at=item.trigger_at.isoformat(),
        status=item.status,
        source_message_id=item.source_message_id,
        scheduler_job_id=item.scheduler_job_id,
        last_error=item.last_error,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def to_ai_model_profile_item(item: "AIModelProfileDefinition") -> AIModelProfileItem:
    return AIModelProfileItem(
        profile_id=item.profile_id,
        name=item.name,
        model_id=item.model_id or "",
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


def to_ai_model_catalog_item(item: "DomainModelCatalogItem") -> AIModelCatalogItem:
    return AIModelCatalogItem(
        id=item.id,
        name=item.name,
    )


def to_ai_relationship_state_item(
    item: "AIRelationshipState",
) -> AIRelationshipStateItem:
    projection = project_emotion(item)
    effective_state = apply_inactivity_decay(
        item,
        current_time=datetime.now(timezone.utc),
    )
    effective_projection = project_emotion(effective_state)
    return AIRelationshipStateItem(
        affinity_id=item.affinity_id,
        platform=item.platform,
        group_id=item.group_id,
        user_id=item.user_id,
        score=item.score,
        mood_tags=list(item.mood_tags),
        last_event_at=item.last_event_at.isoformat() if item.last_event_at else None,
        last_decay_at=item.last_decay_at.isoformat() if item.last_decay_at else None,
        projected_tone=projection.tone,
        warmth_bias=projection.warmth_bias,
        initiative_bias=projection.initiative_bias,
        style_modulation=list(projection.style_modulation),
        effective_score=effective_state.score,
        effective_mood_tags=list(effective_state.mood_tags),
        effective_projected_tone=effective_projection.tone,
        effective_warmth_bias=effective_projection.warmth_bias,
        effective_initiative_bias=effective_projection.initiative_bias,
        effective_style_modulation=list(effective_projection.style_modulation),
    )


def to_ai_relationship_event_item(
    item: "AIRelationshipEvent",
) -> AIRelationshipEventItem:
    return AIRelationshipEventItem(
        event_id=item.event_id,
        affinity_id=item.affinity_id,
        platform=item.platform,
        group_id=item.group_id,
        user_id=item.user_id,
        event_type=item.event_type,
        score_delta=item.score_delta,
        score_after=item.score_after,
        mood_tag=item.mood_tag,
        reason=item.reason,
        created_at=item.created_at.isoformat(),
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
        session_id=item.session_id,
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


def to_ai_person_profile_item(
    item: "AIPersonProfileDefinition",
) -> AIPersonProfileItem:
    return AIPersonProfileItem(
        person_id=item.person_id,
        platform=item.platform,
        user_id=item.user_id,
        person_name=item.person_name,
        nickname=item.nickname,
        name_reason=item.name_reason,
        memory_points=[
            AIPersonMemoryPointItem(
                category=point.category,
                content=point.content,
                confidence=point.confidence,
                source_message_id=point.source_message_id,
            )
            for point in item.memory_points
        ],
        is_known=item.is_known,
        know_since=item.know_since.isoformat() if item.know_since else None,
        last_interaction=item.last_interaction.isoformat(),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
