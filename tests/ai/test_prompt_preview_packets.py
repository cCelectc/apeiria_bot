from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.ai.persona.service import AIPersonaPromptBundle
from apeiria.ai.prompting import PromptPacket, PromptSection, render_flat
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.planning.prompts import RuntimePromptPlanningInput
from apeiria.conversation.models import (
    ChatContextMessageView,
    ChatMessageDetailView,
    ChatSessionAdminView,
    ChatSessionIdentity,
)

if TYPE_CHECKING:
    import pytest

DEFAULT_PROMPT_PREVIEW_LIMIT = 50
APPEND_MESSAGE_ERROR = "prompt preview must not append messages"
SOCIAL_JUDGMENT_ERROR = "prompt preview must not call social judgment model"
PROMPT_PREVIEW_MEMORY_WRITE_ERROR = "prompt preview must not write memories"
PROMPT_PREVIEW_RELATIONSHIP_WRITE_ERROR = (
    "prompt preview must not update relationship state"
)


def test_prompt_preview_exposes_packet_sections_and_rendered_output() -> None:
    module = importlib.import_module("apeiria.app.ai.sessions.prompt_projection")
    project_prompt_packet_to_channels = module.project_prompt_packet_to_channels

    packet = PromptPacket(
        purpose="reply_planner",
        sections=(
            PromptSection(
                role="system",
                name="SystemInstructions",
                content="Plan the reply.",
            ),
            PromptSection(role="system", name="Persona", content="Persona text."),
            PromptSection(role="system", name="ToolPolicy", content="Use tools."),
            PromptSection(role="user", name="Conversation", content="User: hello"),
            PromptSection(role="user", name="Instruction", content="Decide action."),
        ),
    )

    preview = project_prompt_packet_to_channels(packet, mode="planner")

    assert [section.name for section in preview.sections] == [
        "SystemInstructions",
        "Persona",
        "ToolPolicy",
        "Conversation",
        "Instruction",
    ]
    assert preview.tool_policy == "Use tools."
    assert preview.conversation_messages == ("User: hello",)
    assert render_flat(packet).endswith("[Instruction]\nDecide action.")


def test_prompt_preview_reports_region_diagnostics_and_maps_api_schema() -> None:
    module = importlib.import_module("apeiria.app.ai.sessions.prompt_projection")
    models = importlib.import_module("apeiria.app.ai.sessions.models")
    schemas = importlib.import_module("apeiria.webui.routes.ai.sessions_schemas")

    packet = PromptPacket(
        purpose="reply_final",
        sections=(
            PromptSection(
                role="system",
                name="SystemInstructions",
                content="Reply carefully.",
            ),
            PromptSection(role="system", name="Persona", content="Persona text."),
            PromptSection(role="user", name="Conversation", content="User: hello"),
            PromptSection(role="user", name="Instruction", content="Reply now."),
        ),
    )

    channels, diagnostics = module.project_prompt_packet_to_preview(
        packet,
        mode="roleplay",
    )

    assert channels.instruction == "Reply now."
    assert diagnostics.prompt_purpose == "reply_final"
    assert diagnostics.stable_section_names == (
        "SystemInstructions",
        "Persona",
    )
    assert diagnostics.dynamic_section_names == ("Conversation", "Instruction")
    assert "Persona text" not in str(diagnostics)

    preview = models.AISessionPromptPreview(
        session_id="session-1",
        latest_user_message="hello",
        planning_source_id=None,
        planning_profile_id=None,
        planning_model_name=None,
        planning_task_class="reply_default",
        roleplay_source_id=None,
        roleplay_profile_id=None,
        roleplay_model_name=None,
        roleplay_task_class=None,
        source_id=None,
        profile_id=None,
        model_name=None,
        persona_id=None,
        conversation_summary=None,
        relationship_context=None,
        tool_policy=None,
        hard_rule_action="continue",
        hard_rule_reason_text="Private message bypasses ambient initiative budget.",
        hard_rule_reason_codes=("private_message",),
        social_action="reply",
        social_tool_mode="allow",
        social_reason_text="Preview does not call the social judgment model.",
        social_reason_codes=("preview_social_judgment_not_invoked",),
        social_policy_source="preview",
        preview_diagnostics=(
            "social_judgment_model_not_invoked",
            "future_task_metadata_unavailable",
        ),
        tool_results=(),
        memories=(),
        operator_memory_count=0,
        summary_memory_count=0,
        long_term_memory_count=0,
        knowledge_memory_count=0,
        planning_prompt_diagnostics=diagnostics,
        roleplay_prompt_diagnostics=None,
        planning_channels=channels,
        roleplay_channels=None,
        rendered_roleplay_prompt=None,
        rendered_prompt=render_flat(packet),
    )

    item = schemas.to_ai_session_prompt_preview_item(preview)

    assert item.hard_rule_action == "continue"
    assert item.hard_rule_reason_codes == ["private_message"]
    assert item.preview_diagnostics == [
        "social_judgment_model_not_invoked",
        "future_task_metadata_unavailable",
    ]
    assert item.planning_prompt_diagnostics.stable_section_names == [
        "SystemInstructions",
        "Persona",
    ]


def test_prompt_preview_diagnostics_match_runtime_reply_region_projection() -> None:
    from apeiria.ai.prompting import (
        project_reply_prompt_regions,
        prompt_region_diagnostics,
    )
    from apeiria.app.ai.runtime.planning.prompts import (
        RuntimePromptComposeInput,
        build_pre_tool_reply_packet,
    )

    module = importlib.import_module("apeiria.app.ai.sessions.prompt_projection")
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    packet = build_pre_tool_reply_packet(
        RuntimePromptComposeInput(
            persona=None,
            scene_type="private",
            relationship="Relationship context.",
            tool_policy="Tools are available only when they add clear value.",
            tool_results=(),
            memories=[],
            conversation_summary="Conversation summary.",
            social_policy_summary="Preview social policy summary.",
            turns=(
                [
                    ChatContextMessageView(
                        message_id="msg-1",
                        author_role="user",
                        author_id="user-1",
                        author_name="User",
                        text_content="hello",
                        content=None,
                        created_at=now,
                    )
                ]
            ),
            person_profile=("Profile line.",),
        ),
        has_tools=True,
    )

    _channels, diagnostics = module.project_prompt_packet_to_preview(
        packet,
        mode="planner",
    )
    expected = prompt_region_diagnostics(project_reply_prompt_regions(packet))

    assert diagnostics.prompt_purpose == expected["prompt_purpose"]
    assert diagnostics.stable_section_names == expected["stable_section_names"]
    assert diagnostics.dynamic_section_names == expected["dynamic_section_names"]
    assert diagnostics.total_section_count == expected["total_section_count"]


def test_prompt_preview_planning_matches_runtime_prompt_projection() -> None:
    module = importlib.import_module("apeiria.app.ai.sessions.prompt_preview")
    projection = importlib.import_module("apeiria.app.ai.sessions.prompt_projection")
    prompts = importlib.import_module("apeiria.app.ai.runtime.planning.prompts")
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    turn = ChatMessageDetailView(
        message_id="msg-1",
        session_id="session-1",
        platform_message_id="platform-msg-1",
        reply_to_message_id=None,
        platform_reply_id=None,
        author_role="user",
        author_id="user-1",
        author_name="User",
        message_kind="text",
        directed_to_bot=True,
        mentions_bot=True,
        has_media=False,
        text_content="hello",
        content=None,
        meta=None,
        raw_data=None,
        created_at=now,
    )
    preview_turn = module._build_preview_turn(
        identity=identity,
        latest_user_turn=turn,
        latest_user_message="hello",
        user_id="user-1",
    )
    context_bundle = module._build_preview_context_bundle(
        turn=preview_turn,
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
        relationship_target=object(),
        tool_policy=AIToolPolicy(execution_enabled=False),
        persona=None,
        memories=[],
        relationship_context="Relationship context.",
        person_profile=("Profile line.",),
        allowed_tools=(),
    )
    hard_rule_decision = module._build_preview_hard_rule_decision(
        turn=preview_turn,
        now=now,
    )
    social_decision = module._build_preview_social_decision(
        hard_rule_decision=hard_rule_decision,
        has_latest_user_message=True,
    )
    prompt_planning = RuntimePromptPlanningInput(
        skill_runtime=RuntimeToolLoopResult(
            policy_text="Tool policy.",
            result_lines=(),
            turns=(),
        ),
        skill_activation=None,
        has_tools=False,
    )
    context_projection = module._project_preview_context(
        turn=preview_turn,
        context=context_bundle.context,
        prompt_planning=prompt_planning,
        social_decision=social_decision,
    )

    preview_channels, preview_diagnostics, *_ = module._build_preview_prompt_outputs(
        context_projection=context_projection,
        has_tools=False,
        hard_rule_decision=hard_rule_decision,
        social_decision=social_decision,
    )
    packet = prompts.build_initial_reply_prompt_packet(
        turn=preview_turn,
        context=context_bundle.context,
        social_decision=social_decision,
        prompt_input=prompt_planning,
    )
    expected_channels, expected_diagnostics = (
        projection.project_prompt_packet_to_preview(
            packet,
            mode="roleplay",
        )
    )

    assert preview_channels.sections == expected_channels.sections
    assert preview_diagnostics == expected_diagnostics


def test_prompt_preview_uses_context_projection_for_preview_fields() -> None:
    module = importlib.import_module("apeiria.app.ai.sessions.prompt_preview")
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    preview_turn = module._build_preview_turn(
        identity=identity,
        latest_user_turn=None,
        latest_user_message=None,
        user_id="user-1",
    )
    context_bundle = module._build_preview_context_bundle(
        turn=preview_turn,
        turns=[],
        conversation_summary="Conversation summary.",
        relationship_target=object(),
        tool_policy=AIToolPolicy(execution_enabled=False),
        persona=None,
        memories=[],
        relationship_context="Relationship context.",
        person_profile=("Profile line.",),
        allowed_tools=(),
    )
    prompt_planning = RuntimePromptPlanningInput(
        skill_runtime=RuntimeToolLoopResult(
            policy_text="Tool policy.",
            result_lines=("tool result",),
            turns=(),
        ),
        skill_activation=None,
        has_tools=False,
    )

    projection = module._project_preview_context(
        turn=preview_turn,
        context=context_bundle.context,
        social_decision=None,
        prompt_planning=prompt_planning,
    )

    assert projection.prompt.capability_awareness is None
    assert projection.preview.conversation_summary == "Conversation summary."
    assert projection.preview.relationship_context == "Relationship context."
    assert projection.preview.tool_policy_text == "Tool policy."
    assert projection.preview.tool_results == ("tool result",)
    assert projection.preview.memories == ()
    assert projection.diagnostics.as_dict()["projection_mode"] == "preview"


def test_scene_prompt_preview_does_not_call_models_or_execute_tools(  # noqa: C901
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    module = importlib.import_module("apeiria.app.ai.sessions.prompt_preview")
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    conversation = ChatSessionAdminView(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
        title=None,
        summary_text="Conversation summary.",
        created_at=now,
        updated_at=now,
        last_message_at=now,
    )
    turn = ChatMessageDetailView(
        message_id="msg-1",
        session_id="session-1",
        platform_message_id="platform-msg-1",
        reply_to_message_id=None,
        platform_reply_id=None,
        author_role="user",
        author_id="user-1",
        author_name="User",
        message_kind="text",
        directed_to_bot=True,
        mentions_bot=True,
        has_media=False,
        text_content="hello",
        content=None,
        meta=None,
        raw_data=None,
        created_at=now,
    )

    class _ChatSessionService:
        async def get_session_view(self, *, session_id: str):
            assert session_id == "session-1"
            return conversation

        async def get_session_identity(self, *, session_id: str):
            assert session_id == "session-1"
            return identity

        async def list_messages_for_session(self, *, session_id: str, limit: int):
            assert session_id == "session-1"
            assert limit == DEFAULT_PROMPT_PREVIEW_LIMIT
            return [turn]

        async def append_message(self, *_args: object, **_kwargs: object):
            raise AssertionError(APPEND_MESSAGE_ERROR)

    class _PersonaService:
        async def build_persona_prompt_bundle(self, **_kwargs: object):
            return AIPersonaPromptBundle(
                persona_id="persona-1",
                name="Test Persona",
                system_prompt="Persona text.",
                style_prompt="Style text.",
                system_prompt_template="Persona text.",
                style_prompt_template="Style text.",
            )

    class _ToolPolicyBindingService:
        async def resolve_scene_policy(self, **_kwargs: object):
            return AIToolPolicy(execution_enabled=False)

    class _ToolRegistry:
        def list_tools(self):
            return []

    class _ToolService:
        registry = _ToolRegistry()

        def list_allowed_tools(self, _policy: AIToolPolicy):
            return []

    class _ModelSelector:
        async def select_model(self, **_kwargs: object):
            return SimpleNamespace(
                source=SimpleNamespace(source_id="source-1"),
                profile=SimpleNamespace(profile_id="profile-1"),
                resolved_model_name="model-1",
            )

    async def _unexpected_social_judgment(**_kwargs: object):
        raise AssertionError(SOCIAL_JUDGMENT_ERROR)

    async def _retrieve_memories_for_preview(**_kwargs: object):
        return []

    async def _unexpected_memory_write(**_kwargs: object):
        raise AssertionError(PROMPT_PREVIEW_MEMORY_WRITE_ERROR)

    async def _unexpected_relationship_write(**_kwargs: object):
        raise AssertionError(PROMPT_PREVIEW_RELATIONSHIP_WRITE_ERROR)

    monkeypatch.setattr(
        module,
        "ensure_ai_runtime_support_initialized",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(module, "chat_session_service", _ChatSessionService())
    monkeypatch.setattr(module, "ai_persona_service", _PersonaService())
    monkeypatch.setattr(
        module,
        "ai_tool_policy_binding_service",
        _ToolPolicyBindingService(),
    )
    monkeypatch.setattr(module, "ai_tool_service", _ToolService())
    monkeypatch.setattr(module, "ai_model_profile_service", _ModelSelector())
    monkeypatch.setattr(module, "load_relationship_context", _return_relationship)
    monkeypatch.setattr(module, "load_person_profile_for_prompt", _return_profile)
    monkeypatch.setattr(
        module,
        "retrieve_memories_for_preview",
        _retrieve_memories_for_preview,
    )
    monkeypatch.setattr(
        module,
        "store_extracted_memories",
        _unexpected_memory_write,
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "update_relationship_state",
        _unexpected_relationship_write,
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_evaluate_preview_social_judgment",
        _unexpected_social_judgment,
        raising=False,
    )

    preview = asyncio.run(module.build_scene_prompt_preview(scene_id="session-1"))

    assert preview is not None
    assert preview.hard_rule_action == "continue"
    assert preview.social_reason_codes == ("preview_social_judgment_not_invoked",)
    assert "social_judgment_model_not_invoked" in preview.preview_diagnostics
    assert "future_task_metadata_unavailable" in preview.preview_diagnostics


async def _return_relationship(**_kwargs: object) -> str:
    return "Relationship context."


async def _return_profile(**_kwargs: object) -> tuple[str, ...]:
    return ("Profile line.",)
