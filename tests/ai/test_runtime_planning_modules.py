from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from apeiria.ai.capabilities import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
)
from apeiria.ai.model import (
    AIChatModelDefinition,
    AIModelBindingTarget,
    AIModelProfileDefinition,
    AIModelToolDefinition,
    AISourceDefinition,
)
from apeiria.ai.model.runtime.capabilities import AIModelCapabilities
from apeiria.ai.persona.service import AIPersonaPromptBundle
from apeiria.ai.skills.runtime import AISkillSelectionResult
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.planning import turn as planning_module
from apeiria.app.ai.runtime.planning.diagnostics import (
    build_prompt_region_diagnostics,
)
from apeiria.app.ai.runtime.planning.model_selection import (
    select_fallback_models,
    select_model,
)
from apeiria.app.ai.runtime.planning.prompts import (
    RuntimePromptPlanningInput,
    build_initial_reply_prompt_packet,
)
from apeiria.app.ai.runtime.planning.reply_decision import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.runtime.planning.social import project_social_skip_decision
from apeiria.app.ai.runtime.planning.tool_exposure import (
    ToolExposurePlan,
    compile_tool_exposure_provider_schema,
)
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeSourceMediaPart,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.app.ai.runtime.stages import RuntimePlanningInput
from apeiria.conversation.models import ChatContextMessageView, ChatSessionIdentity
from tests.ai.agent_turn_helpers import selected_model


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


def test_runtime_planning_resolves_profile_fallback_candidates(
    monkeypatch: Any,
) -> None:
    from apeiria.ai.model.catalog import chat as chat_module
    from apeiria.ai.model.routing import profile as profile_module
    from apeiria.ai.model.sources import service as source_module

    primary = selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = selected_model("fallback")

    async def list_profiles() -> list[AIModelProfileDefinition]:
        return [primary.profile, fallback.profile]

    async def list_sources() -> list[AISourceDefinition]:
        return [primary.source, fallback.source]

    async def list_models() -> list[AIChatModelDefinition]:
        return [
            AIChatModelDefinition(
                model_id=primary.profile.model_id,
                source_id=primary.source.source_id,
                model_identifier=primary.resolved_model_name or "",
                display_name="Primary",
            ),
            AIChatModelDefinition(
                model_id=fallback.profile.model_id,
                source_id=fallback.source.source_id,
                model_identifier=fallback.resolved_model_name or "",
                display_name="Fallback",
                default_options={"max_tokens": 200},
                capability_metadata={"tool_calling": True},
            ),
        ]

    monkeypatch.setattr(
        profile_module.ai_model_profile_service,
        "list_profiles",
        list_profiles,
    )
    monkeypatch.setattr(source_module.ai_source_service, "list_sources", list_sources)
    monkeypatch.setattr(
        chat_module.ai_chat_model_service,
        "list_all_models",
        list_models,
    )

    candidates = asyncio.run(select_fallback_models(primary, limit=1))

    assert [candidate.profile.profile_id for candidate in candidates] == [
        "profile-fallback"
    ]
    assert candidates[0].resolved_model_name == "model-fallback"
    assert candidates[0].source_model is not None
    assert candidates[0].source_model.model_id == fallback.profile.model_id
    assert candidates[0].model_default_options == {"max_tokens": 200}
    assert candidates[0].resolved_capabilities.supports_tool_calling is True


def test_runtime_planning_model_selection_uses_runtime_names() -> None:
    assert select_model.__name__ == "select_model"
    assert select_fallback_models.__name__ == "select_fallback_models"
    assert select_pre_tool_reply_task_class(has_tools=True) == "tool_orchestration"
    assert select_pre_tool_reply_task_class(has_tools=False) == "reply_default"
    assert select_post_tool_reply_task_class() == "reply_roleplay"


def test_runtime_prompt_planning_builds_initial_reply_packet() -> None:
    now = SimpleNamespace()
    del now
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    turn = SimpleNamespace(
        identity=identity,
        runtime_mode="message",
        future_task=None,
    )
    context = SimpleNamespace(
        persona=AIPersonaPromptBundle(
            persona_id="persona-1",
            name="Test Persona",
            system_prompt="Persona system.",
            style_prompt="Persona style.",
            system_prompt_template="Persona system.",
            style_prompt_template="Persona style.",
        ),
        relationship_context="Relationship context.",
        recalled_memories=[],
        conversation_summary="Conversation summary.",
        person_profile=("Profile line.",),
        allowed_tools=(),
        turns=[
            ChatContextMessageView(
                message_id="msg-1",
                author_role="user",
                author_id="user-1",
                author_name="User",
                text_content="hello",
                content=None,
                created_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
        ],
        rag_chunks=(),
        rag_diagnostics=None,
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("direct_message",),
        reason_text="Reply in direct messages.",
        evidence={},
        decision_source="fallback",
    )
    prompt_input = RuntimePromptPlanningInput(
        skill_runtime=RuntimeToolLoopResult(
            policy_text="Tool policy.",
            result_lines=(),
            turns=(),
        ),
        skill_activation=None,
        has_tools=True,
    )

    packet = build_initial_reply_prompt_packet(
        turn=turn,
        context=context,
        social_decision=social_decision,
        prompt_input=prompt_input,
    )

    assert packet.purpose == "reply_planner"
    assert [section.name for section in packet.sections][:3] == [
        "SystemInstructions",
        "Persona",
        "Style",
    ]
    diagnostics = build_prompt_region_diagnostics(packet)
    assert diagnostics["prompt_purpose"] == "reply_planner"


def test_runtime_initial_reply_messages_project_current_turn_media() -> None:
    from apeiria.app.ai.runtime.planning.turn import (
        build_initial_runtime_reply_prompt_messages,
    )

    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    turn = RuntimeTurnInput(
        identity=identity,
        sender_id="bot-1",
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="look",
            source_message_id="msg-1",
            user_id="user-1",
            is_private=True,
            media_parts=(
                RuntimeSourceMediaPart(
                    kind="image",
                    url="https://cdn.example.test/cat.png",
                    mime_type="image/png",
                    fallback_text="[image: a cat]",
                ),
            ),
        ),
    )
    context = RuntimeContextMaterials(
        turns=[
            ChatContextMessageView(
                message_id="msg-1",
                author_role="user",
                author_id="user-1",
                author_name="User",
                text_content="look",
                content=None,
                created_at=datetime.now(timezone.utc),
            )
        ],
        conversation_summary=None,
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=False),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="avoid",
        reason_codes=("direct_message",),
        reason_text="Reply in direct messages.",
        evidence={},
        decision_source="fallback",
    )
    prompt_input = RuntimePromptPlanningInput(
        skill_runtime=RuntimeToolLoopResult(
            policy_text="Tool policy.",
            result_lines=(),
            turns=(),
        ),
        skill_activation=None,
        has_tools=False,
    )

    messages = build_initial_runtime_reply_prompt_messages(
        turn=turn,
        context=context,
        social_decision=social_decision,
        prompt_input=prompt_input,
    )

    user_messages = [message for message in messages if message.role == "user"]
    assert user_messages[-1].content.endswith("[image: a cat]")
    assert user_messages[-1].parts[-1].kind == "image"


def test_runtime_planning_projects_social_skip_without_old_runtime_types() -> None:
    decision = ReplyStrategyDecision(
        action="silent",
        should_speak=False,
        tool_mode="avoid",
        reason_codes=("ambient_wait",),
        reason_text="wait for more context",
        evidence={"policy_source": "llm"},
        decision_source="llm",
    )

    projection = project_social_skip_decision(decision)

    assert projection.action == "wait"
    assert projection.reason_code == "ambient_merge_window"
    assert projection.should_observe is True
    assert projection.evidence["social_decision_source"] == "llm"


def test_runtime_tool_exposure_planning_exports_provider_schema() -> None:
    provider_tool = AIModelToolDefinition(
        name="memory_query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )

    plan = ToolExposurePlan(selected_tools=(provider_tool,))

    assert compile_tool_exposure_provider_schema(plan) == (provider_tool,)


def test_runtime_planning_uses_runtime_context_materials_for_plan_parity(
    monkeypatch: Any,
) -> None:
    selected = replace(
        selected_model("runtime-plan"),
        resolved_capabilities=AIModelCapabilities(supports_tool_calling=True),
    )
    fallback = selected_model("runtime-fallback")
    captured_selection: list[tuple[str, AIModelBindingTarget]] = []
    captured_skill_selection: list[tuple[str, str | None]] = []
    now = datetime(2026, 5, 6, tzinfo=timezone.utc)
    identity = ChatSessionIdentity(
        session_id="session-plan",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    context = RuntimeContextMaterials(
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
            conversation_id="session-plan",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query"},
        ),
        persona=None,
        recalled_memories=[],
        relationship_context="Relationship context.",
        person_profile=("Profile line.",),
        allowed_tools=(_tool_contract("memory.query"),),
        initiative_bias=0.0,
    )
    turn = RuntimeTurnInput(
        identity=identity,
        sender_id="user-1",
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="msg-1",
            user_id="user-1",
            is_private=True,
        ),
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("direct_message",),
        reason_text="Direct message.",
        evidence={},
        decision_source="llm",
    )

    async def select_runtime_model(
        *,
        task_class: str,
        target: AIModelBindingTarget,
    ):
        captured_selection.append((task_class, target))
        return selected

    async def select_fallbacks(_selected: object):
        return (fallback,)

    async def select_skills(
        *,
        message_text: str,
        conversation_summary: str | None,
    ) -> AISkillSelectionResult:
        captured_skill_selection.append((message_text, conversation_summary))
        return AISkillSelectionResult(
            selected_names=("memory.query",),
            activations=(),
            activation_prompt="Skill active.",
        )

    monkeypatch.setattr(planning_module, "select_model", select_runtime_model)
    monkeypatch.setattr(planning_module, "select_fallback_models", select_fallbacks)
    monkeypatch.setattr(planning_module, "select_runtime_skills", select_skills)

    plan = asyncio.run(
        planning_module.plan_runtime_turn(
            planning_input=RuntimePlanningInput(
                stage="planning",
                trace_id="trace-plan",
                turn=turn,
                context=context,
                social_decision=social_decision,
                current_time=now,
            ),
        )
    )

    assert plan is not None
    assert captured_selection == [("tool_orchestration", context.model_target)]
    assert captured_skill_selection == [("hello", "Conversation summary.")]
    assert plan.selected is selected
    assert plan.fallback_models == (fallback,)
    assert plan.skill_runtime.policy_text
    assert plan.skill_runtime.available_tools
    assert plan.skill_runtime.diagnostics["selected_tool_count"] == 1
    assert plan.skill_activation == "Skill active."
    assert plan.prompt_packet is not None
    assert plan.prompt_packet.purpose == "reply_planner"
    assert plan.prompt_diagnostics["prompt_purpose"] == "reply_planner"
    assert plan.context_projection_diagnostics == {
        "projection_mode": "runtime",
        "turn_count": 1,
        "recalled_memory_count": 0,
        "memory_layers": (),
        "memory_layer_counts": {},
        "has_persona": False,
        "has_relationship_context": True,
        "person_profile_line_count": 1,
        "has_conversation_summary": True,
        "allowed_capability_count": 1,
        "has_capability_awareness": False,
        "has_future_task_context": False,
        "rag_enabled": False,
        "rag_selected_count": 0,
        "rag_candidate_count": 0,
        "rag_missing_embedding_count": 0,
        "rag_stale_embedding_count": 0,
        "rag_rerank_status": None,
        "rag_degradation_reason": None,
    }
    assert plan.tool_exposure_plan.selected_tool_names == ("memory.query",)


def test_runtime_planning_replans_exposure_after_model_selection(
    monkeypatch: Any,
) -> None:
    selected = replace(
        selected_model("runtime-plan"),
        resolved_capabilities=AIModelCapabilities(supports_tool_calling=False),
    )
    now = datetime(2026, 5, 6, tzinfo=timezone.utc)
    identity = ChatSessionIdentity(
        session_id="session-plan",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    context = RuntimeContextMaterials(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="session-plan",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(
            execution_enabled=True,
            allowed_tool_names={"memory.query"},
        ),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(_tool_contract("memory.query"),),
        initiative_bias=0.0,
    )
    turn = RuntimeTurnInput(
        identity=identity,
        sender_id="user-1",
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="msg-1",
            user_id="user-1",
            is_private=True,
        ),
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("direct_message",),
        reason_text="Direct message.",
        evidence={},
        decision_source="llm",
    )

    async def select_runtime_model(
        *,
        task_class: str,
        target: AIModelBindingTarget,
    ):
        del task_class, target
        return selected

    async def select_fallbacks(_selected: object):
        return ()

    async def select_skills(
        *,
        message_text: str,
        conversation_summary: str | None,
    ) -> AISkillSelectionResult:
        del message_text, conversation_summary
        return AISkillSelectionResult(
            selected_names=(),
            activations=(),
            activation_prompt=None,
        )

    monkeypatch.setattr(planning_module, "select_model", select_runtime_model)
    monkeypatch.setattr(planning_module, "select_fallback_models", select_fallbacks)
    monkeypatch.setattr(planning_module, "select_runtime_skills", select_skills)

    plan = asyncio.run(
        planning_module.plan_runtime_turn(
            planning_input=RuntimePlanningInput(
                stage="planning",
                trace_id="trace-plan",
                turn=turn,
                context=context,
                social_decision=social_decision,
                current_time=now,
            ),
        )
    )

    assert plan is not None
    assert plan.pre_tool_task_class == "tool_orchestration"
    assert plan.has_executable_tools is False
    assert plan.skill_runtime.available_tools == ()
    assert plan.tool_exposure_plan.unavailable_reasons == {
        "memory.query": "selected model does not support tools"
    }


def test_runtime_planning_no_longer_imports_old_pipeline_helpers() -> None:
    source = Path("apeiria/app/ai/runtime/planning/turn.py").read_text()
    forbidden = (
        "apeiria.app.ai.pipeline.composer",
        "apeiria.app.ai.pipeline.model_steps",
        "apeiria.app.ai.pipeline.routing",
        "select_pipeline_model",
        "select_pipeline_fallback_models",
    )

    assert not [name for name in forbidden if name in source]
