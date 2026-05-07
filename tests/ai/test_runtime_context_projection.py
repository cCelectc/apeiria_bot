from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from apeiria.ai.capabilities import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
)
from apeiria.ai.memory import AIMemoryDefinition
from apeiria.ai.model import AIModelBindingTarget
from apeiria.ai.persona.service import AIPersonaPromptBundle
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.conversation.models import ChatContextMessageView, ChatSessionIdentity


def _tool_contract(name: str) -> AICapabilityContract:
    return AICapabilityContract(
        name=name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description="Recall memory",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
        tags=("memory",),
    )


def _memory(
    *,
    memory_id: str,
    layer: str,
    content: str,
    now: datetime,
) -> AIMemoryDefinition:
    return AIMemoryDefinition(
        memory_id=memory_id,
        anchor_type="user",
        anchor_id="user-1",
        memory_layer=layer,  # type: ignore[arg-type]
        memory_kind="fact",
        content=content,
        is_editable=True,
        is_ignored=False,
        source_message_id=None,
        salience=0.8,
        confidence=0.9,
        last_recalled_at=None,
        created_at=now,
    )


def _turn(now: datetime) -> RuntimeTurnInput:
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    return RuntimeTurnInput(
        identity=identity,
        sender_id="bot-1",
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="msg-1",
            user_id="user-1",
            is_private=True,
        ),
        future_task=AIFutureTaskDefinition(
            task_id="task-1",
            session_id="session-1",
            platform="test",
            scene_type="private",
            scene_id="user-1",
            user_id="user-1",
            title="Follow up",
            description="Ask for the final answer.",
            trigger_at=now,
            status="pending",
            source_message_id=None,
            scheduler_job_id=None,
            last_error=None,
            created_at=now,
            updated_at=now,
        ),
    )


def _context(now: datetime) -> RuntimeContextMaterials:
    return RuntimeContextMaterials(
        turns=[
            ChatContextMessageView(
                message_id="msg-1",
                author_role="user",
                author_id="user-1",
                author_name="User",
                text_content="hello",
                content=None,
                created_at=now,
            )
        ],
        conversation_summary="Conversation summary.",
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=True),
        persona=AIPersonaPromptBundle(
            persona_id="persona-1",
            name="Test Persona",
            system_prompt="Persona system.",
            style_prompt="Persona style.",
            system_prompt_template="Persona system.",
            style_prompt_template="Persona style.",
        ),
        recalled_memories=[
            _memory(
                memory_id="memory-1",
                layer="long_term",
                content="Known fact.",
                now=now,
            ),
            _memory(
                memory_id="memory-2",
                layer="summary",
                content="Summary fact.",
                now=now,
            ),
        ],
        relationship_context="Relationship context.",
        person_profile=("Profile line 1.", "Profile line 2."),
        allowed_tools=(_tool_contract("memory.query"),),
        initiative_bias=0.25,
    )


def _social_decision() -> ReplyStrategyDecision:
    return ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("direct_message",),
        reason_text="Direct message.",
        evidence={"policy_source": "preview"},
        decision_source="fallback",
    )


def test_runtime_context_projection_preserves_prompt_fields() -> None:
    from apeiria.app.ai.runtime.context.projection import project_runtime_context

    now = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
    context = _context(now)
    turn = _turn(now)
    skill_runtime = RuntimeToolLoopResult(
        policy_text="Tool policy.",
        result_lines=("tool result",),
        turns=(),
    )

    projection = project_runtime_context(
        turn=turn,
        context=context,
        social_decision=_social_decision(),
        skill_runtime=skill_runtime,
        skill_activation="Skill active.",
    )

    prompt = projection.prompt
    assert prompt.persona is context.persona
    assert prompt.scene_type == "private"
    assert prompt.relationship == "Relationship context."
    assert prompt.tool_policy == "Tool policy."
    assert prompt.tool_results == ("tool result",)
    assert prompt.memories == tuple(context.recalled_memories)
    assert prompt.turns == tuple(context.turns)
    assert prompt.person_profile == ("Profile line 1.", "Profile line 2.")
    assert prompt.conversation_summary == "Conversation summary."
    assert "Action: reply" in (prompt.social_policy_summary or "")
    assert "task_id=task-1" in (prompt.future_task_context or "")
    assert prompt.skill_activation == "Skill active."
    assert prompt.capability_awareness is None

    assert projection.preview.persona is context.persona
    assert projection.preview.relationship_context == "Relationship context."
    assert projection.preview.conversation_summary == "Conversation summary."
    assert projection.preview.tool_policy_text == "Tool policy."
    assert projection.preview.tool_results == ("tool result",)
    assert projection.preview.memories == tuple(context.recalled_memories)
    assert projection.preview.capability_awareness is None


def test_runtime_context_projection_emits_bounded_shape_diagnostics() -> None:
    from apeiria.app.ai.runtime.context.projection import project_runtime_context

    now = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
    context = _context(now)
    expected_memory_count = 2
    expected_profile_lines = 2

    projection = project_runtime_context(
        turn=replace(_turn(now), future_task=None),
        context=context,
        social_decision=_social_decision(),
        skill_runtime=RuntimeToolLoopResult(
            policy_text="Tool policy.",
            result_lines=(),
            turns=(),
        ),
        projection_mode="preview",
    )

    diagnostics = projection.diagnostics
    assert diagnostics.projection_mode == "preview"
    assert diagnostics.turn_count == 1
    assert diagnostics.recalled_memory_count == expected_memory_count
    assert diagnostics.memory_layers == ("long_term", "summary")
    assert diagnostics.has_persona is True
    assert diagnostics.has_relationship_context is True
    assert diagnostics.person_profile_line_count == expected_profile_lines
    assert diagnostics.has_conversation_summary is True
    assert diagnostics.allowed_capability_count == 1
    assert diagnostics.has_future_task_context is False
    assert "Known fact." not in str(diagnostics)
    assert diagnostics.as_dict() == {
        "projection_mode": "preview",
        "turn_count": 1,
        "recalled_memory_count": 2,
        "memory_layers": ("long_term", "summary"),
        "has_persona": True,
        "has_relationship_context": True,
        "person_profile_line_count": 2,
        "has_conversation_summary": True,
        "allowed_capability_count": 1,
        "has_capability_awareness": False,
        "has_future_task_context": False,
    }
