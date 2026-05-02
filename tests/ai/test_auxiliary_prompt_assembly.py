from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from apeiria.ai.memory import AIMemoryDefinition
from apeiria.ai.model import AIModelMessage, AIModelToolCall, AISelectedModel
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
from apeiria.ai.tools.models import AIToolSpec
from apeiria.app.ai.reply_strategy.models import SocialJudgmentInput
from apeiria.conversation.models import ChatContextMessageView
from tests.ai.agent_turn_helpers import model_response, selected_model


@dataclass(frozen=True)
class _SkillEntry:
    skill_name: str
    description: str
    entry_mode: str = "prompt_only"


class _ModelGateway:
    def __init__(
        self,
        content: str,
        *,
        tool_calls: tuple[AIModelToolCall, ...] = (),
    ) -> None:
        self.selected = selected_model("aux")
        self.content = content
        self.tool_calls = tool_calls
        self.prompts: list[str] = []
        self.message_calls: list[tuple[AIModelMessage, ...]] = []
        self.tool_def_calls: list[tuple[Any, ...]] = []

    async def select_model(self, **_: object):
        return self.selected

    async def generate_native(
        self,
        *,
        selected: AISelectedModel,
        prompt: str = "",
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[Any, ...] = (),
    ):
        self.prompts.append(prompt)
        self.message_calls.append(messages)
        self.tool_def_calls.append(tools)
        return model_response(selected, self.content, tool_calls=self.tool_calls)


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

    gateway = _ModelGateway(
        '{"action":"reply","tool_mode":"avoid","reason_codes":["ok"],'
        '"reason_text":"ok","evidence":{}}'
    )
    monkeypatch.setattr(social_judgment, "model_gateway", gateway)

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
    assert gateway.prompts == [""]
    assert gateway.message_calls[0]
    assert "[OutputContract]" in gateway.message_calls[0][-1].content


def test_memory_extraction_uses_rendered_messages(monkeypatch: Any) -> None:
    from apeiria.app.ai.pipeline import memory_extraction_steps

    gateway = _ModelGateway(
        '{"memories":[{"memory_kind":"fact","content":"likes tea",'
        '"confidence":0.9,"salience":0.8}],'
        '"sentiment":{"polarity":"positive","intensity":0.5},'
        '"self_introduction_name":null}'
    )
    monkeypatch.setattr(memory_extraction_steps, "model_gateway", gateway)

    result = asyncio.run(
        memory_extraction_steps.extract_memory_from_message(
            message_text="I like tea",
            existing_memories=(_memory(),),
        )
    )

    assert result.candidates[0].content == "likes tea"
    assert gateway.prompts == [""]
    assert "[ExistingMemories]" in gateway.message_calls[0][-1].content


def test_summary_and_skill_selection_use_rendered_messages(monkeypatch: Any) -> None:
    from apeiria.ai import model as model_module
    from apeiria.ai.model.runtime import gateway as runtime_gateway
    from apeiria.ai.skills.selection import AISkillSelector
    from apeiria.app.ai.conversation_context.summary import (
        compress_conversation_history,
    )

    summary_gateway = _ModelGateway("new summary")
    monkeypatch.setattr(model_module, "model_gateway", summary_gateway)

    summary = asyncio.run(
        compress_conversation_history(
            [_turn("user", "hello", name="Alice")],
            existing_summary=None,
            scene_type="private",
        )
    )

    assert summary == "new summary"
    assert summary_gateway.prompts == [""]
    assert "[ConversationHistory]" in summary_gateway.message_calls[0][-1].content

    skill_gateway = _ModelGateway('["drawing"]')
    monkeypatch.setattr(runtime_gateway, "model_gateway", skill_gateway)

    selected = asyncio.run(
        AISkillSelector().select_skill_names(
            message_text="draw this",
            conversation_summary="old topic",
            entries=[_SkillEntry("drawing", "Draw things")],
        )
    )

    assert selected == ["drawing"]
    assert skill_gateway.prompts == [""]
    assert "[SkillCatalog]" in skill_gateway.message_calls[0][-1].content


def test_tool_intent_planning_uses_messages_and_tools(monkeypatch: Any) -> None:
    from apeiria.ai.model.runtime import gateway as runtime_gateway
    from apeiria.ai.tools.planning import AIToolIntentPlanner

    gateway = _ModelGateway(
        "",
        tool_calls=(
            AIModelToolCall(
                tool_call_id="call-1",
                name="memory_query",
                arguments={"query_text": "hello"},
            ),
        ),
    )
    monkeypatch.setattr(runtime_gateway, "model_gateway", gateway)

    intents = asyncio.run(
        AIToolIntentPlanner().plan_tool_intents(
            message_text="search memory",
            allowed_tools=[
                AIToolSpec(
                    name="memory.query",
                    description="Search memory",
                    read_only=True,
                    concurrency_safe=True,
                )
            ],
            recalled_memory_ids=("m1",),
            recalled_memory_contents=("known fact",),
            relationship_context="friendly",
        )
    )

    assert intents[0].tool_name == "memory.query"
    assert gateway.prompts == [""]
    assert gateway.tool_def_calls[0]
    assert "[RecalledMemories]" in gateway.message_calls[0][-1].content
