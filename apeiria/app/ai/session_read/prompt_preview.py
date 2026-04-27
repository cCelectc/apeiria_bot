"""Prompt-preview assembly for AI session workbench reads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.access.groups import group_service
from apeiria.ai.model import AIModelBindingTarget, AIModelRouteQuery, ai_model_facade
from apeiria.ai.persona import (
    AIPersonaBindingTarget,
    ai_persona_service,
    build_persona_render_context,
)
from apeiria.ai.prompting import render_flat
from apeiria.ai.tools import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
    ai_tool_service,
    summarize_tool_policy,
)
from apeiria.app.ai.admin.workbench import (
    extract_tool_result_lines,
    select_latest_user_turn,
    to_context_turns,
)
from apeiria.app.ai.pipeline.composer import (
    AIRuntimeComposeInput,
    build_pre_tool_reply_packet,
    build_roleplay_reply_packet,
)
from apeiria.app.ai.pipeline.memory_steps import retrieve_memories_for_preview
from apeiria.app.ai.pipeline.person_profile_steps import load_person_profile_for_prompt
from apeiria.app.ai.pipeline.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.pipeline.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.reply_strategy import (
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
    summarize_reply_strategy_decision,
)
from apeiria.app.ai.tooling import ensure_app_ai_tools_loaded
from apeiria.conversation.service import chat_session_service

from .models import (
    AISessionPromptChannels,
    AISessionPromptPreview,
    AISessionPromptSection,
)
from .prompt_projection import project_prompt_packet_to_channels

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.app.ai.reply_strategy.models import (
        ReplyStrategyDecision,
        SocialJudgmentInput,
    )
    from apeiria.conversation.models import (
        ChatContextMessageView,
        ChatMessageDetailView,
        ChatSessionIdentity,
    )


def _build_prompt_preview_social_input(  # noqa: PLR0913
    *,
    session_id: str,
    identity: "ChatSessionIdentity",
    latest_user_message: str,
    conversation_summary: str | None,
    relationship_context: str | None,
    persona_id: str | None,
    allowed_tool_names: tuple[str, ...],
    context_turns: list["ChatContextMessageView"],
):
    from apeiria.app.ai.reply_strategy.models import SocialJudgmentInput

    decision_time = (
        latest_bot_turn_at(context_turns) or context_turns[-1].created_at
        if context_turns
        else datetime.now(timezone.utc)
    )
    return SocialJudgmentInput(
        session_id=session_id,
        scene_type=identity.scene_type,
        message_text=latest_user_message,
        latest_user_turn_text=latest_user_turn_text(context_turns),
        conversation_summary=conversation_summary,
        relationship_context=relationship_context,
        persona_id=persona_id,
        available_tool_names=allowed_tool_names,
        recent_turn_count=len(context_turns),
        recent_bot_turn_count=count_recent_bot_turns(context_turns),
        last_bot_turn_at=latest_bot_turn_at(context_turns),
        current_time=decision_time,
        runtime_mode="message",
        engagement_type="direct",
        initiative_budget_score=None,
        consecutive_silence_count=0,
    )


async def _evaluate_preview_social_judgment(
    *,
    judgment_input: "SocialJudgmentInput",
    target: "AIModelBindingTarget",
) -> "ReplyStrategyDecision":
    """Run social judgment for workbench preview and wrap as ReplyStrategyDecision."""

    from apeiria.app.ai.reply_strategy.models import judgment_to_decision
    from apeiria.app.ai.reply_strategy.social_judgment import (
        evaluate_social_judgment,
    )

    result = await evaluate_social_judgment(
        judgment_input=judgment_input,
        target=target,
    )
    return judgment_to_decision(result)


def _find_recent_user_name(
    turns: "Sequence[ChatContextMessageView | ChatMessageDetailView]",
    user_id: str,
) -> str | None:
    for turn in reversed(turns):
        if turn.author_role != "user" or turn.author_id != user_id:
            continue
        author_name = (turn.author_name or "").strip()
        if author_name:
            return author_name
    return None


async def _load_group_name(identity: "ChatSessionIdentity") -> str | None:
    if identity.scene_type != "group":
        return None
    group = await group_service.get_group(identity.scene_id)
    return group.group_name if group is not None else None


async def build_scene_prompt_preview(
    *,
    scene_id: str,
    turn_limit: int = 50,
) -> AISessionPromptPreview | None:
    ensure_app_ai_tools_loaded()
    conversation = await chat_session_service.get_session_view(session_id=scene_id)
    if conversation is None:
        return None
    identity = await chat_session_service.get_session_identity(session_id=scene_id)
    if identity is None:
        return None
    turns = await chat_session_service.list_messages_for_session(
        session_id=scene_id,
        limit=turn_limit,
    )
    latest_user_turn = select_latest_user_turn(turns)
    latest_user_message = (
        latest_user_turn.text_content.strip() if latest_user_turn is not None else None
    )
    user_id = identity.subject_id or (
        latest_user_turn.author_id if latest_user_turn is not None else None
    )
    prompt_time = turns[-1].created_at if turns else datetime.now(timezone.utc)
    group_name = await _load_group_name(identity)
    relationship_context = None
    if user_id is not None:
        relationship_target = build_relationship_target(identity, user_id)
        relationship_context = await load_relationship_context(
            target=relationship_target,
        )
    persona = await ai_persona_service.build_persona_prompt_bundle(
        target=AIPersonaBindingTarget(
            conversation_id=identity.session_id,
            group_id=identity.scene_id if identity.scene_type == "group" else None,
            user_id=user_id,
        ),
        render_context=build_persona_render_context(
            bot_id=identity.bot_id,
            current_time=prompt_time,
            platform=identity.platform,
            scene_type=identity.scene_type,
            scene_id=identity.scene_id,
            session_id=identity.session_id,
            group_name=group_name,
            user_id=user_id,
            user_name=(
                _find_recent_user_name(turns, user_id) if user_id is not None else None
            )
            or user_id,
        ),
    )
    tool_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
        scene_context=AIToolSceneContext(
            scope_type=identity.scene_type,
            is_tome=identity.scene_type == "private",
        ),
        target=AIToolPolicyBindingTarget(
            conversation_id=identity.session_id,
            group_id=identity.scene_id if identity.scene_type == "group" else None,
            user_id=user_id,
        ),
    )
    memories = (
        await retrieve_memories_for_preview(
            identity=identity,
            user_id=user_id,
            query_text=latest_user_message or "",
        )
        if latest_user_message and user_id is not None
        else []
    )
    tool_results = extract_tool_result_lines(turns)
    tool_policy_text = summarize_tool_policy(
        ai_tool_service.registry.list_tools(),
        tool_policy,
    )
    person_profile = (
        await load_person_profile_for_prompt(
            identity=identity,
            user_id=user_id,
        )
        if user_id is not None
        else ()
    )
    allowed_tools = ai_tool_service.list_allowed_tools(tool_policy)
    has_tools = bool(allowed_tools)
    pre_tool_task_class = select_pre_tool_reply_task_class(has_tools=has_tools)
    selected = await ai_model_facade.select_model(
        query=AIModelRouteQuery(task_class=pre_tool_task_class),
        target=AIModelBindingTarget(
            conversation_id=identity.session_id,
            group_id=identity.scene_id if identity.scene_type == "group" else None,
            user_id=user_id,
        ),
    )
    roleplay_selected = (
        await ai_model_facade.select_model(
            query=AIModelRouteQuery(task_class=select_post_tool_reply_task_class()),
            target=AIModelBindingTarget(
                conversation_id=identity.session_id,
                group_id=identity.scene_id if identity.scene_type == "group" else None,
                user_id=user_id,
            ),
        )
        if has_tools
        else None
    )
    context_turns = to_context_turns(turns)
    social_decision = (
        await _evaluate_preview_social_judgment(
            judgment_input=_build_prompt_preview_social_input(
                session_id=scene_id,
                identity=identity,
                latest_user_message=latest_user_message,
                conversation_summary=conversation.summary_text,
                relationship_context=relationship_context,
                persona_id=persona.persona_id if persona is not None else None,
                allowed_tool_names=tuple(tool.name for tool in allowed_tools),
                context_turns=context_turns,
            ),
            target=AIModelBindingTarget(
                conversation_id=identity.session_id,
                group_id=identity.scene_id if identity.scene_type == "group" else None,
                user_id=user_id,
            ),
        )
        if latest_user_message
        else None
    )
    compose_input = AIRuntimeComposeInput(
        persona=persona,
        scene_type=identity.scene_type,
        person_profile=person_profile,
        relationship=relationship_context,
        tool_policy=tool_policy_text,
        tool_results=tool_results,
        memories=memories,
        conversation_summary=conversation.summary_text,
        social_policy_summary=(
            summarize_reply_strategy_decision(social_decision)
            if social_decision is not None
            else None
        ),
        turns=context_turns,
    )
    planning_packet = build_pre_tool_reply_packet(compose_input, has_tools=has_tools)
    planning_mode = "planner" if has_tools else "roleplay"
    planning_channels = (
        project_prompt_packet_to_channels(planning_packet, mode=planning_mode)
        if social_decision is None or social_decision.should_speak
        else AISessionPromptChannels(
            mode=planning_mode,
            system_instructions=(),
            persona="",
            style=None,
            relationship=None,
            person_profile=(),
            social_policy=None,
            tool_policy=None,
            future_task=None,
            tool_results=(),
            operator_memories=(),
            summary_memories=(),
            long_term_memories=(),
            knowledge_memories=(),
            conversation_summary=None,
            context_priority=(),
            conversation_messages=(),
            response_rules=(),
            instruction="Suppressed by social policy before prompt generation.",
            sections=(
                AISessionPromptSection(
                    role="system",
                    name="Suppressed",
                    content="Suppressed by social policy before prompt generation.",
                ),
            ),
        )
    )
    rendered_prompt = (
        render_flat(planning_packet)
        if social_decision is None or social_decision.should_speak
        else "Suppressed by social policy before prompt generation."
    )
    roleplay_packet = build_roleplay_reply_packet(compose_input)
    roleplay_channels = (
        project_prompt_packet_to_channels(roleplay_packet, mode="roleplay")
        if has_tools and (social_decision is None or social_decision.should_speak)
        else None
    )
    rendered_roleplay_prompt = (
        render_flat(roleplay_packet)
        if has_tools and (social_decision is None or social_decision.should_speak)
        else None
    )
    operator_memory_count = sum(
        1 for memory in memories if memory.memory_layer == "operator"
    )
    summary_memory_count = sum(
        1 for memory in memories if memory.memory_layer == "summary"
    )
    long_term_memory_count = sum(
        1 for memory in memories if memory.memory_layer == "long_term"
    )
    knowledge_memory_count = sum(
        1 for memory in memories if memory.memory_layer == "knowledge"
    )
    return AISessionPromptPreview(
        session_id=scene_id,
        latest_user_message=latest_user_message,
        planning_source_id=selected.source.source_id if selected is not None else None,
        planning_profile_id=(
            selected.profile.profile_id if selected is not None else None
        ),
        planning_model_name=(
            selected.resolved_model_name if selected is not None else None
        ),
        planning_task_class=pre_tool_task_class,
        roleplay_source_id=(
            roleplay_selected.source.source_id
            if roleplay_selected is not None
            else None
        ),
        roleplay_profile_id=(
            roleplay_selected.profile.profile_id
            if roleplay_selected is not None
            else None
        ),
        roleplay_model_name=(
            roleplay_selected.resolved_model_name
            if roleplay_selected is not None
            else None
        ),
        roleplay_task_class=select_post_tool_reply_task_class() if has_tools else None,
        source_id=selected.source.source_id if selected is not None else None,
        profile_id=selected.profile.profile_id if selected is not None else None,
        model_name=selected.resolved_model_name if selected is not None else None,
        persona_id=persona.persona_id if persona is not None else None,
        conversation_summary=conversation.summary_text,
        relationship_context=relationship_context,
        tool_policy=tool_policy_text,
        social_action=social_decision.action if social_decision is not None else None,
        social_tool_mode=(
            social_decision.tool_mode if social_decision is not None else None
        ),
        social_reason_text=(
            social_decision.reason_text if social_decision is not None else None
        ),
        social_reason_codes=(
            social_decision.reason_codes if social_decision is not None else ()
        ),
        social_policy_source=(
            str(social_decision.evidence.get("policy_source"))
            if social_decision is not None
            and social_decision.evidence.get("policy_source") is not None
            else None
        ),
        tool_results=tool_results,
        memories=tuple(memories),
        operator_memory_count=operator_memory_count,
        summary_memory_count=summary_memory_count,
        long_term_memory_count=long_term_memory_count,
        knowledge_memory_count=knowledge_memory_count,
        planning_channels=planning_channels,
        roleplay_channels=roleplay_channels,
        rendered_roleplay_prompt=rendered_roleplay_prompt if has_tools else None,
        rendered_prompt=rendered_prompt,
    )


__all__ = ["build_scene_prompt_preview"]
