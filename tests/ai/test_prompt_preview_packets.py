from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.ai.persona.service import AIPersonaPromptBundle
from apeiria.ai.prompting import PromptPacket, PromptSection, render_flat
from apeiria.ai.tools import AIToolPolicy
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
TOOL_EXECUTION_ERROR = "prompt preview must not execute tools"
MODEL_CALL_ERROR = "prompt preview must not call provider models"
SOCIAL_JUDGMENT_ERROR = "prompt preview must not call social judgment model"


def test_prompt_preview_exposes_packet_sections_and_rendered_output() -> None:
    module = importlib.import_module("apeiria.app.ai.session_read.prompt_projection")
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
    module = importlib.import_module("apeiria.app.ai.session_read.prompt_projection")
    models = importlib.import_module("apeiria.app.ai.session_read.models")
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
    from apeiria.app.ai.pipeline.composer import (
        AIRuntimeComposeInput,
        build_pre_tool_reply_packet,
    )

    module = importlib.import_module("apeiria.app.ai.session_read.prompt_projection")
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    packet = build_pre_tool_reply_packet(
        AIRuntimeComposeInput(
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


def test_prompt_preview_uses_central_packet_projection() -> None:
    project_root = Path(__file__).resolve().parents[2]
    preview_source = (
        project_root / "apeiria" / "app" / "ai" / "session_read" / "prompt_preview.py"
    ).read_text(encoding="utf-8")

    assert "project_prompt_packet_to_preview" in preview_source
    assert "_to_prompt_channel_preview" not in preview_source
    assert "def _section_text" not in preview_source
    assert "def _section_lines" not in preview_source


def test_prompt_preview_keeps_mutating_runtime_steps_out_of_read_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    preview_source = (
        project_root / "apeiria" / "app" / "ai" / "session_read" / "prompt_preview.py"
    ).read_text(encoding="utf-8")

    assert "retrieve_memories_for_preview" in preview_source
    for mutating_step in (
        "build_and_store_context_window",
        "store_extracted_memories",
        "update_relationship_state",
        "recall_memories(",
        "record_context_usage",
        "generate_model_turn",
        "append_tool_observation_turns",
        "observe_read_only_tools",
        "execute_tool",
    ):
        assert mutating_step not in preview_source


def test_scene_prompt_preview_does_not_call_models_or_execute_tools(  # noqa: C901
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    module = importlib.import_module("apeiria.app.ai.session_read.prompt_preview")
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

        async def observe_read_only_tools(self, *_args: object, **_kwargs: object):
            raise AssertionError(TOOL_EXECUTION_ERROR)

    class _ModelFacade:
        async def select_model(self, **_kwargs: object):
            return SimpleNamespace(
                source=SimpleNamespace(source_id="source-1"),
                profile=SimpleNamespace(profile_id="profile-1"),
                resolved_model_name="model-1",
            )

        async def generate(self, *_args: object, **_kwargs: object):
            raise AssertionError(MODEL_CALL_ERROR)

    async def _unexpected_social_judgment(**_kwargs: object):
        raise AssertionError(SOCIAL_JUDGMENT_ERROR)

    async def _retrieve_memories_for_preview(**_kwargs: object):
        return []

    monkeypatch.setattr(module, "ensure_app_ai_tools_loaded", lambda: None)
    monkeypatch.setattr(module, "chat_session_service", _ChatSessionService())
    monkeypatch.setattr(module, "ai_persona_service", _PersonaService())
    monkeypatch.setattr(
        module,
        "ai_tool_policy_binding_service",
        _ToolPolicyBindingService(),
    )
    monkeypatch.setattr(module, "ai_tool_service", _ToolService())
    monkeypatch.setattr(module, "ai_model_facade", _ModelFacade())
    monkeypatch.setattr(module, "load_relationship_context", _return_relationship)
    monkeypatch.setattr(module, "load_person_profile_for_prompt", _return_profile)
    monkeypatch.setattr(
        module,
        "retrieve_memories_for_preview",
        _retrieve_memories_for_preview,
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
