"""Pure mapping helpers for AI admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.interfaces.http.schemas.ai_models import (
    AIMemoryItem,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIRelationshipStateItem,
    AIToolExecutionItem,
    AIToolItem,
)

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )
    from apeiria.app.ai.relationship.models import AIRelationshipState
    from apeiria.app.ai.tools.models import AIToolExecutionView, AIToolSpec


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
