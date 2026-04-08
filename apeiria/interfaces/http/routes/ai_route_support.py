"""Pure mapping helpers for AI admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.interfaces.http.schemas.ai_models import (
    AICapabilityItem,
    AICapabilityPreviewItem,
    AIMemoryItem,
    AIModelBindingItem,
    AIModelProfileItem,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIProviderItem,
    AIProviderModelItem,
    AIRelationshipStateItem,
    AIToolExecutionItem,
    AIToolItem,
    AIToolPolicyPreviewItem,
)

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.models.bindings import AIModelBindingSpec
    from apeiria.app.ai.models.models import AIModelProfileDefinition
    from apeiria.app.ai.models.provider import (
        AIProviderModelItem as DomainProviderModelItem,
    )
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )
    from apeiria.app.ai.providers.models import AIProviderDefinition
    from apeiria.app.ai.relationship.models import AIRelationshipState
    from apeiria.app.ai.tools.models import (
        AICapabilityDefinition,
        AICapabilityPreview,
        AIToolExecutionView,
        AIToolPolicy,
        AIToolSpec,
    )


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
