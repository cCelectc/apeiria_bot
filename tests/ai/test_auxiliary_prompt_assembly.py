from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from apeiria.ai.capabilities import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
)
from apeiria.ai.memory import AIMemoryDefinition
from apeiria.ai.model import AIModelMessage, AIModelToolCall, AISelectedModel
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallOptions,
    AIModelCallRequirements,
    AIModelCapabilities,
)
from apeiria.ai.model.runtime.planning import plan_model_call
from apeiria.ai.prompting import (
    ConversationSummaryPromptInput,
    MemoryExtractionPromptInput,
    SkillSelectionPromptInput,
    SocialJudgmentPromptInput,
    ToolIntentPlanningPromptInput,
    build_conversation_summary_packet,
    build_memory_extraction_packet,
    build_skill_selection_packet,
    build_social_judgment_packet,
    build_tool_intent_planning_packet,
    render_messages,
)
from apeiria.app.ai.reply_strategy.models import SocialJudgmentInput
from apeiria.conversation.models import ChatContextMessageView
from tests.ai.agent_turn_helpers import model_response, selected_model


@dataclass(frozen=True)
class _SkillEntry:
    skill_name: str
    description: str
    entry_mode: str = "prompt_only"
    origin: str = "file"


class _ModelSelector:
    def __init__(self, selected: AISelectedModel | None) -> None:
        self.selected = selected
        self.queries: list[Any] = []

    async def select_model(self, **kwargs: object):
        self.queries.append(dict(kwargs))
        return self.selected


class _ModelInvoker:
    def __init__(
        self,
        content: str | BaseException,
        *,
        selected: AISelectedModel | None = None,
        tool_calls: tuple[AIModelToolCall, ...] = (),
        plan_options: bool = False,
    ) -> None:
        self.selected = selected or selected_model("aux")
        self.content = content
        self.tool_calls = tool_calls
        self.plan_options = plan_options
        self.message_calls: list[tuple[AIModelMessage, ...]] = []
        self.tool_def_calls: list[tuple[Any, ...]] = []
        self.option_calls: list[AIModelCallOptions | None] = []
        self.planned_option_calls: list[dict[str, Any]] = []
        self.degradation_calls: list[tuple[Any, ...]] = []

    async def generate_text(  # noqa: PLR0913
        self,
        *,
        selected: AISelectedModel,
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[Any, ...] = (),
        requirements: AIModelCallRequirements | None = None,
        options: AIModelCallOptions | None = None,
        call_options: dict[str, Any] | None = None,
    ):
        self.message_calls.append(messages)
        self.tool_def_calls.append(tools)
        self.option_calls.append(options)
        if self.plan_options:
            plan = plan_model_call(
                selected=selected,
                messages=messages,
                tools=tools,
                requirements=requirements,
                options=options,
                call_options=call_options,
            )
            self.planned_option_calls.append(plan.options)
            self.degradation_calls.append(plan.degradations)
        if isinstance(self.content, BaseException):
            raise self.content
        return model_response(selected, self.content, tool_calls=self.tool_calls)


def _patch_selector_and_invoker(
    monkeypatch: Any,
    module: Any,
    invoker: _ModelInvoker,
) -> None:
    monkeypatch.setattr(
        module,
        "ai_model_profile_service",
        _ModelSelector(invoker.selected),
    )
    monkeypatch.setattr(module, "model_invoker", invoker)


def _memory(layer: str = "long_term") -> AIMemoryDefinition:
    return AIMemoryDefinition(
        memory_id=f"memory-{layer}",
        anchor_type="user",
        anchor_id="user-1",
        memory_layer=layer,  # type: ignore[arg-type]
        memory_kind="fact",
        content="likes tea",
        is_editable=True,
        is_ignored=False,
        source_message_id=None,
        salience=0.8,
        confidence=0.7,
        last_recalled_at=None,
        created_at=datetime.now(timezone.utc),
    )


def _turn(role: str, text: str, *, name: str | None = None) -> ChatContextMessageView:
    return ChatContextMessageView(
        message_id=f"msg-{role}",
        author_role=role,  # type: ignore[arg-type]
        author_id=f"{role}-1",
        author_name=name,
        text_content=text,
        content=None,
        created_at=datetime.now(timezone.utc),
    )


def test_auxiliary_recipes_build_ordered_packets_and_messages() -> None:
    social = build_social_judgment_packet(
        SocialJudgmentPromptInput(
            scene_type="group",
            runtime_mode="message",
            engagement_type="direct",
            message_text="hello",
            latest_user_turn_text="hello",
            conversation_summary=None,
            relationship_context=None,
            persona_id=None,
            available_tool_names=("memory.query",),
            recent_turn_count=2,
            recent_bot_turn_count=0,
            consecutive_silence_count=1,
            current_time=datetime.now(timezone.utc),
        )
    )
    memory = build_memory_extraction_packet(
        MemoryExtractionPromptInput(message_text="call me Alice")
    )
    summary = build_conversation_summary_packet(
        ConversationSummaryPromptInput(
            overflow_messages=(_turn("user", "hello", name="Alice"),),
            existing_summary="old summary",
            scene_type="group",
        )
    )
    skill = build_skill_selection_packet(
        SkillSelectionPromptInput(
            message_text="please draw",
            conversation_summary=None,
            entries=(_SkillEntry("drawing", "Draw things"),),
        )
    )
    tool = build_tool_intent_planning_packet(
        ToolIntentPlanningPromptInput(
            message_text="remember this",
            recalled_memory_ids=(),
            recalled_memory_contents=(),
            relationship_context=None,
        )
    )

    assert social.purpose == "social_judgment"
    assert [section.name for section in social.sections] == [
        "Instruction",
        "EngagementPolicy",
        "ActionPolicy",
        "Context",
        "OutputContract",
    ]
    assert memory.purpose == "memory_extraction"
    assert "ExistingMemories" not in [section.name for section in memory.sections]
    assert summary.purpose == "conversation_summary"
    assert "ExistingSummary" in [section.name for section in summary.sections]
    assert skill.purpose == "skill_selection"
    assert "SkillCatalog" in [section.name for section in skill.sections]
    assert tool.purpose == "tool_intent_planning"
    assert "RecalledMemories" not in [section.name for section in tool.sections]

    messages = render_messages(social)
    assert [message.role for message in messages] == ["system", "user"]
    assert "[EngagementPolicy]" in messages[0].content
    assert "[OutputContract]" in messages[1].content


def test_auxiliary_renderer_handles_business_names_generically() -> None:
    packet = build_tool_intent_planning_packet(
        ToolIntentPlanningPromptInput(
            message_text="use memory",
            recalled_memory_ids=("m1",),
            recalled_memory_contents=("known fact",),
            relationship_context="friendly",
        )
    )

    rendered = render_messages(packet)

    assert rendered[-1].role == "user"
    assert "[RecalledMemories]\n- m1: known fact" in rendered[-1].content
    assert "[RelationshipContext]\nfriendly" in rendered[-1].content


def test_social_judgment_generation_uses_rendered_messages(monkeypatch: Any) -> None:
    from apeiria.app.ai.reply_strategy import social_judgment

    invoker = _ModelInvoker(
        '{"action":"reply","tool_mode":"avoid","reason_codes":["ok"],'
        '"reason_text":"ok","evidence":{}}'
    )
    _patch_selector_and_invoker(monkeypatch, social_judgment, invoker)

    result = asyncio.run(
        social_judgment.evaluate_social_judgment(
            judgment_input=SocialJudgmentInput(
                session_id="session-1",
                scene_type="private",
                message_text="hello",
                latest_user_turn_text="hello",
                conversation_summary=None,
                relationship_context=None,
                persona_id=None,
                available_tool_names=(),
                recent_turn_count=1,
                recent_bot_turn_count=0,
                last_bot_turn_at=None,
                current_time=datetime.now(timezone.utc),
                runtime_mode="message",
                engagement_type="direct",
                initiative_budget_score=None,
                consecutive_silence_count=0,
            )
        )
    )

    assert result.action == "reply"
    assert invoker.message_calls[0]
    assert "[OutputContract]" in invoker.message_calls[0][-1].content


def test_social_judgment_requests_structured_output_schema(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.reply_strategy import social_judgment

    invoker = _ModelInvoker(
        '{"action":"reply","tool_mode":"avoid","reason_codes":["ok"],'
        '"reason_text":"ok","evidence":{}}',
        selected=_selected_model_with_capabilities(
            AIModelCapabilities(supports_structured_output=True)
        ),
        plan_options=True,
    )
    _patch_selector_and_invoker(monkeypatch, social_judgment, invoker)

    result = asyncio.run(
        social_judgment.evaluate_social_judgment(
            judgment_input=_social_judgment_input()
        )
    )

    assert result.action == "reply"
    requested_options = invoker.option_calls[0]
    assert requested_options is not None
    response_format = requested_options.values["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "social_judgment"
    assert "action" in response_format["json_schema"]["schema"]["required"]
    assert invoker.planned_option_calls[0]["response_format"] == response_format
    assert "[OutputContract]" in invoker.message_calls[0][-1].content


def test_memory_extraction_requests_structured_output_schema(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.runtime.context import memory_extraction

    invoker = _ModelInvoker(
        '{"memories":[{"memory_kind":"fact","content":"likes tea",'
        '"confidence":0.9,"salience":0.8}],'
        '"sentiment":{"polarity":"positive","intensity":0.5},'
        '"self_introduction_name":null}',
        selected=_selected_model_with_capabilities(
            AIModelCapabilities(supports_structured_output=True)
        ),
        plan_options=True,
    )
    _patch_selector_and_invoker(monkeypatch, memory_extraction, invoker)

    result = asyncio.run(
        memory_extraction.extract_memory_from_message(
            message_text="I like tea",
            existing_memories=(_memory(),),
        )
    )

    assert result.candidates[0].content == "likes tea"
    requested_options = invoker.option_calls[0]
    assert requested_options is not None
    response_format = requested_options.values["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "memory_extraction"
    assert response_format["json_schema"]["schema"]["required"] == [
        "memories",
        "sentiment",
        "self_introduction_name",
    ]
    assert invoker.planned_option_calls[0]["response_format"] == response_format


def test_memory_extraction_invalid_or_failed_structured_output_uses_empty_result(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.runtime.context import memory_extraction

    selected = _selected_model_with_capabilities(
        AIModelCapabilities(supports_structured_output=True)
    )
    invalid_invoker = _ModelInvoker("not-json", selected=selected)
    _patch_selector_and_invoker(monkeypatch, memory_extraction, invalid_invoker)

    invalid = asyncio.run(
        memory_extraction.extract_memory_from_message(
            message_text="I like tea",
            existing_memories=(_memory(),),
        )
    )

    failing_invoker = _ModelInvoker(
        RuntimeError("provider rejected response_format"),
        selected=selected,
    )
    _patch_selector_and_invoker(monkeypatch, memory_extraction, failing_invoker)

    failed = asyncio.run(
        memory_extraction.extract_memory_from_message(
            message_text="I like tea",
            existing_memories=(_memory(),),
        )
    )

    assert invalid.candidates == []
    assert invalid.sentiment.polarity == "neutral"
    assert invalid.self_introduction_name is None
    assert failed.candidates == []
    assert failed.sentiment.polarity == "neutral"
    assert failed.self_introduction_name is None


def test_skill_selection_requests_object_structured_output_schema(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.runtime.planning import skills as runtime_skills

    invoker = _ModelInvoker(
        '{"selected_names":["drawing","unknown","drawing"]}',
        selected=_selected_model_with_capabilities(
            AIModelCapabilities(supports_structured_output=True)
        ),
        plan_options=True,
    )
    monkeypatch.setattr(
        runtime_skills,
        "ai_model_profile_service",
        _ModelSelector(invoker.selected),
    )
    monkeypatch.setattr(runtime_skills, "model_invoker", invoker)
    monkeypatch.setattr(
        runtime_skills.ai_skill_runtime,
        "list_catalog",
        lambda: [_SkillEntry("drawing", "Draw things")],
    )

    result = asyncio.run(
        runtime_skills.select_runtime_skills(
            message_text="draw this",
            conversation_summary="old topic",
        )
    )

    assert result.selected_names == ("drawing",)
    requested_options = invoker.option_calls[0]
    assert requested_options is not None
    response_format = requested_options.values["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "skill_selection"
    assert response_format["json_schema"]["schema"]["required"] == [
        "selected_names",
    ]
    assert invoker.planned_option_calls[0]["response_format"] == response_format


def test_skill_selection_invalid_structured_output_uses_empty_result(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.runtime.planning import skills as runtime_skills

    invoker = _ModelInvoker(
        '{"selected_names":"drawing"}',
        selected=_selected_model_with_capabilities(
            AIModelCapabilities(supports_structured_output=True)
        ),
    )
    monkeypatch.setattr(
        runtime_skills,
        "ai_model_profile_service",
        _ModelSelector(invoker.selected),
    )
    monkeypatch.setattr(runtime_skills, "model_invoker", invoker)
    monkeypatch.setattr(
        runtime_skills.ai_skill_runtime,
        "list_catalog",
        lambda: [_SkillEntry("drawing", "Draw things")],
    )

    result = asyncio.run(
        runtime_skills.select_runtime_skills(
            message_text="draw this",
            conversation_summary=None,
        )
    )

    assert result.selected_names == ()


def test_auxiliary_prompt_output_contracts_match_structured_shapes() -> None:
    social_packet = build_social_judgment_packet(
        SocialJudgmentPromptInput(
            scene_type="group",
            runtime_mode="message",
            engagement_type="direct",
            message_text="hello",
            latest_user_turn_text="hello",
            conversation_summary=None,
            relationship_context=None,
            persona_id=None,
            available_tool_names=(),
            recent_turn_count=1,
            recent_bot_turn_count=0,
            consecutive_silence_count=0,
            current_time=datetime.now(timezone.utc),
        )
    )
    memory_packet = build_memory_extraction_packet(
        MemoryExtractionPromptInput(message_text="call me Alice")
    )
    skill_packet = build_skill_selection_packet(
        SkillSelectionPromptInput(
            message_text="please draw",
            conversation_summary=None,
            entries=(_SkillEntry("drawing", "Draw things"),),
        )
    )

    social_contract = _section_content(social_packet, "OutputContract")
    memory_contract = _section_content(memory_packet, "OutputContract")
    skill_contract = _section_content(skill_packet, "OutputContract")

    assert '"action"' in social_contract
    assert '"tool_mode"' in social_contract
    assert '"memories"' in memory_contract
    assert '"sentiment"' in memory_contract
    assert '"self_introduction_name"' in memory_contract
    assert '"selected_names"' in skill_contract
    assert "JSON array" not in skill_contract


def test_social_judgment_degrades_schema_to_json_object_when_only_json_mode(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.reply_strategy import social_judgment

    invoker = _ModelInvoker(
        '{"action":"reply","tool_mode":"avoid","reason_codes":["ok"],'
        '"reason_text":"ok","evidence":{}}',
        selected=_selected_model_with_capabilities(
            AIModelCapabilities(supports_json_mode=True)
        ),
        plan_options=True,
    )
    _patch_selector_and_invoker(monkeypatch, social_judgment, invoker)

    asyncio.run(
        social_judgment.evaluate_social_judgment(
            judgment_input=_social_judgment_input()
        )
    )

    assert invoker.planned_option_calls[0]["response_format"] == {"type": "json_object"}
    assert invoker.degradation_calls[0][0].kind == "structured_output_degraded"


def test_skill_runtime_selection_projects_prompt_skill_capabilities() -> None:
    from apeiria.ai.skills.parser import AISkillFileDefinition
    from apeiria.ai.skills.runtime import AISkillRuntime

    runtime = AISkillRuntime()
    runtime.register_file_skills(
        [
            AISkillFileDefinition(
                skill_name="drawing",
                description="Draw things",
                version=1,
                triggers=(),
                permissions=(),
                entry_mode="prompt_only",
                body_markdown="Use simple drawing instructions.",
                file_path="<test>",
                tools=("memory.query",),
                tags=("creative",),
            )
        ]
    )

    result = runtime.build_selection_result(selected_names=("drawing",))

    assert result.activation_prompt is not None
    assert tuple(activation.name for activation in result.prompt_activations) == (
        "drawing",
    )
    assert result.prompt_activations[0].required_capabilities == ("memory.query",)
    assert result.prompt_activations[0].body_markdown == (
        "Use simple drawing instructions."
    )


def test_social_judgment_omits_native_response_format_when_unsupported(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.reply_strategy import social_judgment

    invoker = _ModelInvoker(
        '{"action":"reply","tool_mode":"avoid","reason_codes":["ok"],'
        '"reason_text":"ok","evidence":{}}',
        selected=_selected_model_with_capabilities(AIModelCapabilities()),
        plan_options=True,
    )
    _patch_selector_and_invoker(monkeypatch, social_judgment, invoker)

    asyncio.run(
        social_judgment.evaluate_social_judgment(
            judgment_input=_social_judgment_input()
        )
    )

    assert "response_format" not in invoker.planned_option_calls[0]
    assert invoker.degradation_calls[0][0].kind == "structured_output_omitted"
    assert "[OutputContract]" in invoker.message_calls[0][-1].content


def test_social_judgment_invalid_or_failed_structured_output_uses_fallback(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.reply_strategy import social_judgment

    selected = _selected_model_with_capabilities(
        AIModelCapabilities(supports_structured_output=True)
    )
    invalid_invoker = _ModelInvoker(
        '{"action":"invalid","tool_mode":"avoid","reason_codes":["bad"],'
        '"reason_text":"bad","evidence":{}}',
        selected=selected,
    )
    _patch_selector_and_invoker(monkeypatch, social_judgment, invalid_invoker)

    invalid = asyncio.run(
        social_judgment.evaluate_social_judgment(
            judgment_input=_social_judgment_input()
        )
    )

    failing_invoker = _ModelInvoker(
        RuntimeError("provider rejected response_format"),
        selected=selected,
    )
    _patch_selector_and_invoker(monkeypatch, social_judgment, failing_invoker)

    failed = asyncio.run(
        social_judgment.evaluate_social_judgment(
            judgment_input=_social_judgment_input()
        )
    )

    assert invalid.reason_codes == ("fallback_social_judgment",)
    assert invalid.evidence["policy_source"] == "fallback"
    assert failed.reason_codes == ("fallback_social_judgment",)
    assert failed.evidence["policy_source"] == "fallback"


def test_memory_extraction_uses_rendered_messages(monkeypatch: Any) -> None:
    from apeiria.app.ai.runtime.context import memory_extraction

    invoker = _ModelInvoker(
        '{"memories":[{"memory_kind":"fact","content":"likes tea",'
        '"confidence":0.9,"salience":0.8}],'
        '"sentiment":{"polarity":"positive","intensity":0.5},'
        '"self_introduction_name":null}'
    )
    _patch_selector_and_invoker(monkeypatch, memory_extraction, invoker)

    result = asyncio.run(
        memory_extraction.extract_memory_from_message(
            message_text="I like tea",
            existing_memories=(_memory(),),
        )
    )

    assert result.candidates[0].content == "likes tea"
    assert "[ExistingMemories]" in invoker.message_calls[0][-1].content


def test_summary_and_skill_selection_use_rendered_messages(monkeypatch: Any) -> None:
    from apeiria.ai import model as model_module
    from apeiria.ai.model.routing import profile as profile_module
    from apeiria.app.ai.conversation_context.summary import (
        compress_conversation_history,
    )
    from apeiria.app.ai.runtime.planning import skills as runtime_skills

    summary_invoker = _ModelInvoker("new summary")
    monkeypatch.setattr(model_module, "model_invoker", summary_invoker)
    monkeypatch.setattr(
        profile_module,
        "ai_model_profile_service",
        _ModelSelector(summary_invoker.selected),
    )

    summary = asyncio.run(
        compress_conversation_history(
            [_turn("user", "hello", name="Alice")],
            existing_summary=None,
            scene_type="private",
        )
    )

    assert summary == "new summary"
    assert "[ConversationHistory]" in summary_invoker.message_calls[0][-1].content

    skill_invoker = _ModelInvoker('{"selected_names":["drawing"]}')
    monkeypatch.setattr(
        runtime_skills,
        "ai_model_profile_service",
        _ModelSelector(skill_invoker.selected),
    )
    monkeypatch.setattr(runtime_skills, "model_invoker", skill_invoker)
    monkeypatch.setattr(
        runtime_skills.ai_skill_runtime,
        "list_catalog",
        lambda: [_SkillEntry("drawing", "Draw things")],
    )

    result = asyncio.run(
        runtime_skills.select_runtime_skills(
            message_text="draw this",
            conversation_summary="old topic",
        )
    )

    assert result.selected_names == ("drawing",)
    assert "[SkillCatalog]" in skill_invoker.message_calls[0][-1].content


def test_tool_intent_planning_uses_messages_and_tools(monkeypatch: Any) -> None:
    from apeiria.app.ai.runtime.planning import tool_intents

    invoker = _ModelInvoker(
        "",
        tool_calls=(
            AIModelToolCall(
                tool_call_id="call-1",
                name="memory_query",
                arguments={"query_text": "hello"},
            ),
        ),
    )
    monkeypatch.setattr(
        tool_intents,
        "ai_model_profile_service",
        _ModelSelector(invoker.selected),
    )
    monkeypatch.setattr(tool_intents, "model_invoker", invoker)
    monkeypatch.setattr(
        tool_intents,
        "ai_tool_service",
        type(
            "ToolService",
            (),
            {
                "list_allowed_tools": lambda _self, _policy: [
                    AICapabilityContract(
                        name="memory.query",
                        kind=AICapabilityKind.EXECUTABLE,
                        origin=AICapabilityOrigin.BUILTIN,
                        description="Search memory",
                        safety=AICapabilitySafety(
                            read_only=True,
                            risk_level="low",
                            concurrency_safe=True,
                        ),
                    )
                ]
            },
        )(),
    )

    intents = asyncio.run(
        tool_intents.plan_runtime_tool_intents(
            message_text="search memory",
            policy=object(),  # type: ignore[arg-type]
            recalled_memory_ids=("m1",),
            recalled_memory_contents=("known fact",),
            relationship_context="friendly",
        )
    )

    assert intents[0].tool_name == "memory.query"
    assert invoker.tool_def_calls[0]
    assert "[RecalledMemories]" in invoker.message_calls[0][-1].content


def _selected_model_with_capabilities(
    capabilities: AIModelCapabilities,
) -> AISelectedModel:
    return replace(
        selected_model("aux"),
        resolved_capabilities=capabilities,
    )


def _social_judgment_input() -> SocialJudgmentInput:
    return SocialJudgmentInput(
        session_id="session-1",
        scene_type="private",
        message_text="hello",
        latest_user_turn_text="hello",
        conversation_summary=None,
        relationship_context=None,
        persona_id=None,
        available_tool_names=(),
        recent_turn_count=1,
        recent_bot_turn_count=0,
        last_bot_turn_at=None,
        current_time=datetime.now(timezone.utc),
        runtime_mode="message",
        engagement_type="direct",
        initiative_budget_score=None,
        consecutive_silence_count=0,
    )


def _section_content(packet: Any, name: str) -> str:
    for section in packet.sections:
        if section.name == name:
            return str(section.content)
    msg = f"missing section {name}"
    raise AssertionError(msg)
