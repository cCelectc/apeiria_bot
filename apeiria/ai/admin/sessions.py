"""Session / scene / prompt-preview admin operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.access.groups import group_service
from apeiria.ai.admin.types import (
    AIRecentTarget,
    AISessionPromptChannels,
    AISessionPromptPreview,
)
from apeiria.ai.admin.workbench import (
    extract_tool_result_lines,
    select_latest_user_turn,
    to_context_turns,
)
from apeiria.ai.conversation.identity import build_participant_subject_id
from apeiria.ai.conversation.service import chat_session_service
from apeiria.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.ai.model.service import ai_model_facade
from apeiria.ai.persona.models import AIPersonaBindingTarget
from apeiria.ai.persona.service import (
    ai_persona_service,
    build_persona_render_context,
)
from apeiria.ai.pipeline.composer import (
    AIRuntimeComposeInput,
    build_runtime_prompt_channels,
    compose_pre_tool_reply_prompt,
    compose_roleplay_reply_prompt,
)
from apeiria.ai.pipeline.memory_steps import (
    load_person_profile_for_prompt,
    retrieve_memories_for_preview,
)
from apeiria.ai.pipeline.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.ai.pipeline.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.ai.reply_strategy import (
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
    summarize_reply_strategy_decision,
)
from apeiria.ai.tools.policy import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
    summarize_tool_policy,
)
from apeiria.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.ai.conversation.models import (
        ChatContextMessageView,
        ChatMessageDetailView,
        ChatSessionAdminView,
        ChatSessionIdentity,
    )
    from apeiria.ai.pipeline.prompting import AIReplyPromptChannels
    from apeiria.ai.reply_strategy.models import (
        ReplyStrategyDecision,
        SocialJudgmentInput,
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
    from apeiria.ai.reply_strategy.models import SocialJudgmentInput

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
    session: "AsyncSession",
    *,
    judgment_input: "SocialJudgmentInput",
    target: "AIModelBindingTarget",
) -> "ReplyStrategyDecision":
    """Run social judgment for workbench preview and wrap as ReplyStrategyDecision."""

    from apeiria.ai.reply_strategy.models import judgment_to_decision
    from apeiria.ai.reply_strategy.social_judgment import (
        evaluate_social_judgment,
    )

    result = await evaluate_social_judgment(
        session,
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


def _to_prompt_channel_preview(
    channels: "AIReplyPromptChannels",
) -> AISessionPromptChannels:
    return AISessionPromptChannels(
        mode=channels.mode,
        system_instructions=channels.system.instructions,
        persona=channels.system.persona,
        style=channels.system.style,
        relationship=channels.system.relationship,
        social_policy=channels.system.social_policy,
        tool_policy=channels.system.tool_policy,
        future_task=channels.system.future_task,
        person_profile=channels.person_profile,
        tool_results=channels.tool_results,
        operator_memories=channels.memories.operator,
        summary_memories=channels.memories.summary,
        long_term_memories=channels.memories.long_term,
        knowledge_memories=channels.memories.knowledge,
        conversation_summary=channels.conversation.summary,
        context_priority=channels.conversation.context_priority,
        conversation_messages=channels.conversation.messages,
        response_rules=channels.response_rules,
        instruction=channels.instruction,
    )


class SessionsAdminMixin:
    """Admin read for recent sessions, scene turns, and scene prompt preview."""

    async def list_recent_sessions(
        self,
        *,
        limit: int = 20,
    ) -> list["ChatSessionAdminView"]:
        async with get_session() as session:
            return await chat_session_service.list_recent_sessions(
                session,
                limit=limit,
            )

    async def list_recent_targets(
        self,
        *,
        limit: int = 20,
    ) -> list[AIRecentTarget]:
        sessions = await self.list_recent_sessions(limit=limit)
        targets: list[AIRecentTarget] = []
        seen_users: set[str] = set()
        seen_participants: set[str] = set()

        async with get_session() as session:
            for item in sessions:
                summary = (item.summary_text or "").strip()
                conversation_title = summary or item.session_id[:12]
                conversation_subtitle = (
                    f"{item.platform} · {item.scene_type} · {item.scene_id}"
                )
                targets.append(
                    AIRecentTarget(
                        target_type="scene",
                        anchor_type="scene",
                        anchor_id=item.session_id,
                        title=conversation_title,
                        subtitle=conversation_subtitle,
                        scene_id=item.session_id,
                        platform=item.platform,
                        scope_type=item.scene_type,
                        scope_id=item.scene_id,
                        user_id=item.subject_id,
                        last_active_at=item.last_message_at.isoformat(),
                    )
                )

                if item.scene_type == "group":
                    participant_user_ids = await (
                        chat_session_service.list_recent_user_ids_for_session(
                            session,
                            session_id=item.session_id,
                            limit=3,
                        )
                    )
                else:
                    participant_user_ids = [item.subject_id or item.scene_id]

                for user_id in participant_user_ids:
                    if not user_id:
                        continue
                    if item.scene_type == "group":
                        participant_id = build_participant_subject_id(
                            scene_type=item.scene_type,
                            scene_id=item.scene_id,
                            user_id=user_id,
                        )
                        if participant_id not in seen_participants:
                            seen_participants.add(participant_id)
                            targets.append(
                                AIRecentTarget(
                                    target_type="participant",
                                    anchor_type="participant",
                                    anchor_id=participant_id,
                                    title=user_id,
                                    subtitle=f"{item.platform} · group participant",
                                    scene_id=item.session_id,
                                    platform=item.platform,
                                    scope_type=item.scene_type,
                                    scope_id=item.scene_id,
                                    user_id=user_id,
                                    last_active_at=item.last_message_at.isoformat(),
                                )
                            )
                    if user_id in seen_users:
                        continue
                    seen_users.add(user_id)
                    user_subtitle = f"{item.platform} · {item.scene_type}"
                    targets.append(
                        AIRecentTarget(
                            target_type="user",
                            anchor_type="user",
                            anchor_id=user_id,
                            title=user_id,
                            subtitle=user_subtitle,
                            scene_id=item.session_id,
                            platform=item.platform,
                            scope_type=item.scene_type,
                            scope_id=item.scene_id,
                            user_id=user_id,
                            last_active_at=item.last_message_at.isoformat(),
                        )
                    )

        return targets[: limit * 2]

    async def list_scene_turns(
        self,
        *,
        scene_id: str,
        limit: int = 50,
    ) -> list["ChatMessageDetailView"]:
        async with get_session() as session:
            return await chat_session_service.list_messages_for_session(
                session,
                session_id=scene_id,
                limit=limit,
            )

    async def build_scene_prompt_preview(
        self,
        *,
        scene_id: str,
        turn_limit: int = 50,
    ) -> AISessionPromptPreview | None:
        async with get_session() as session:
            conversation = await chat_session_service.get_session_view(
                session,
                session_id=scene_id,
            )
            if conversation is None:
                return None
            identity = await chat_session_service.get_session_identity(
                session,
                session_id=scene_id,
            )
            if identity is None:
                return None
            turns = await chat_session_service.list_messages_for_session(
                session,
                session_id=scene_id,
                limit=turn_limit,
            )
            latest_user_turn = select_latest_user_turn(turns)
            latest_user_message = (
                latest_user_turn.text_content.strip()
                if latest_user_turn is not None
                else None
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
                    session,
                    target=relationship_target,
                )
            persona = await ai_persona_service.build_persona_prompt_bundle(
                session,
                target=AIPersonaBindingTarget(
                    conversation_id=identity.session_id,
                    group_id=(
                        identity.scene_id if identity.scene_type == "group" else None
                    ),
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
                        _find_recent_user_name(turns, user_id)
                        if user_id is not None
                        else None
                    )
                    or user_id,
                ),
            )
            tool_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
                session,
                scene_context=AIToolSceneContext(
                    scope_type=identity.scene_type,
                    is_tome=identity.scene_type == "private",
                ),
                target=AIToolPolicyBindingTarget(
                    conversation_id=identity.session_id,
                    group_id=(
                        identity.scene_id if identity.scene_type == "group" else None
                    ),
                    user_id=user_id,
                ),
            )
            memories = (
                await retrieve_memories_for_preview(
                    session,
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
                    session,
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
                session,
                query=AIModelRouteQuery(task_class=pre_tool_task_class),
                target=AIModelBindingTarget(
                    conversation_id=identity.session_id,
                    group_id=(
                        identity.scene_id if identity.scene_type == "group" else None
                    ),
                    user_id=user_id,
                ),
            )
            roleplay_selected = (
                await ai_model_facade.select_model(
                    session,
                    query=AIModelRouteQuery(
                        task_class=select_post_tool_reply_task_class()
                    ),
                    target=AIModelBindingTarget(
                        conversation_id=identity.session_id,
                        group_id=(
                            identity.scene_id
                            if identity.scene_type == "group"
                            else None
                        ),
                        user_id=user_id,
                    ),
                )
                if has_tools
                else None
            )
            context_turns = to_context_turns(turns)
            social_decision = (
                await _evaluate_preview_social_judgment(
                    session,
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
                        group_id=(
                            identity.scene_id
                            if identity.scene_type == "group"
                            else None
                        ),
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
            planning_channels = (
                _to_prompt_channel_preview(
                    build_runtime_prompt_channels(
                        compose_input,
                        mode="planner" if has_tools else "roleplay",
                        include_tool_policy=has_tools,
                    )
                )
                if social_decision is None or social_decision.should_speak
                else AISessionPromptChannels(
                    mode="planner" if has_tools else "roleplay",
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
                )
            )
            rendered_prompt = (
                compose_pre_tool_reply_prompt(
                    compose_input,
                    has_tools=has_tools,
                )
                if social_decision is None or social_decision.should_speak
                else "Suppressed by social policy before prompt generation."
            )
            roleplay_channels = (
                _to_prompt_channel_preview(
                    build_runtime_prompt_channels(
                        compose_input,
                        mode="roleplay",
                        include_tool_policy=False,
                    )
                )
                if has_tools
                and (social_decision is None or social_decision.should_speak)
                else None
            )
            rendered_roleplay_prompt = (
                compose_roleplay_reply_prompt(compose_input)
                if has_tools
                and (social_decision is None or social_decision.should_speak)
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
                planning_source_id=(
                    selected.source.source_id if selected is not None else None
                ),
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
                roleplay_task_class=(
                    select_post_tool_reply_task_class() if has_tools else None
                ),
                source_id=(selected.source.source_id if selected is not None else None),
                profile_id=(
                    selected.profile.profile_id if selected is not None else None
                ),
                model_name=(
                    selected.resolved_model_name if selected is not None else None
                ),
                persona_id=persona.persona_id if persona is not None else None,
                conversation_summary=conversation.summary_text,
                relationship_context=relationship_context,
                tool_policy=tool_policy_text,
                social_action=(
                    social_decision.action if social_decision is not None else None
                ),
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
                rendered_roleplay_prompt=(
                    rendered_roleplay_prompt if has_tools else None
                ),
                rendered_prompt=rendered_prompt,
            )


__all__ = ["SessionsAdminMixin"]
