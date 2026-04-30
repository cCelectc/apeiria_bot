"""Prompt-preview assembly for AI session workbench reads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.access.groups import group_service
from apeiria.ai.model import AIModelRouteQuery, ai_model_facade
from apeiria.ai.persona import (
    ai_persona_service,
    build_persona_render_context,
)
from apeiria.ai.prompting import render_flat
from apeiria.ai.tools import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ToolGatewayResult,
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
    build_roleplay_reply_packet,
)
from apeiria.app.ai.pipeline.generation_steps import (
    ReplyPromptPlanningInput,
    build_initial_reply_prompt_packet,
)
from apeiria.app.ai.pipeline.input_steps import ReplyInputs
from apeiria.app.ai.pipeline.memory_steps import retrieve_memories_for_preview
from apeiria.app.ai.pipeline.person_profile_steps import load_person_profile_for_prompt
from apeiria.app.ai.pipeline.persona_steps import (
    build_model_binding_target,
    build_persona_binding_target,
)
from apeiria.app.ai.pipeline.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.pipeline.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
from apeiria.app.ai.reply_strategy import summarize_reply_strategy_decision
from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.session_runtime import (
    RuntimeContextBundle,
    RuntimeHardRuleDecision,
    RuntimeTurnSource,
    decide_runtime_hard_rule,
)
from apeiria.app.ai.tooling import ensure_app_ai_tools_loaded
from apeiria.conversation.service import chat_session_service

from .models import (
    AISessionPromptChannels,
    AISessionPromptDiagnostics,
    AISessionPromptPreview,
    AISessionPromptSection,
)
from .prompt_projection import project_prompt_packet_to_preview

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.conversation.models import (
        ChatContextMessageView,
        ChatMessageDetailView,
        ChatSessionIdentity,
    )


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


def _preview_direct_signal(
    *,
    identity: "ChatSessionIdentity",
    latest_user_turn: "ChatMessageDetailView | None",
) -> bool:
    return identity.scene_type == "private" or bool(
        latest_user_turn is not None
        and (latest_user_turn.directed_to_bot or latest_user_turn.mentions_bot)
    )


def _build_preview_request(
    *,
    identity: "ChatSessionIdentity",
    latest_user_turn: "ChatMessageDetailView | None",
    latest_user_message: str | None,
    user_id: str,
) -> AIRuntimeReplyRequest:
    """Normalize preview inputs into the same request shape as live runtime."""

    return AIRuntimeReplyRequest(
        identity=identity,
        message_text=latest_user_message or "",
        source_message_id=(
            latest_user_turn.message_id if latest_user_turn is not None else None
        ),
        user_id=user_id,
        sender_id=identity.bot_id,
        runtime_mode="message",
        is_tome=_preview_direct_signal(
            identity=identity,
            latest_user_turn=latest_user_turn,
        ),
        event_dedupe_key=(
            latest_user_turn.platform_message_id
            if latest_user_turn is not None
            else None
        ),
        event_dedupe_claimed=True,
    )


def _build_preview_context_bundle(  # noqa: PLR0913
    *,
    request: AIRuntimeReplyRequest,
    turns: list["ChatContextMessageView"],
    conversation_summary: str | None,
    relationship_target: object,
    tool_policy: object,
    persona: object | None,
    memories: "Sequence[object]",
    relationship_context: str | None,
    person_profile: tuple[str, ...],
    allowed_tools: "Sequence[object]",
) -> RuntimeContextBundle:
    """Build preview-safe context without mutating runtime state."""

    return RuntimeContextBundle(
        stage="context",
        inputs=ReplyInputs(
            turns=turns,  # type: ignore[arg-type]
            conversation_summary=conversation_summary,
            relationship_target=relationship_target,  # type: ignore[arg-type]
            model_target=build_model_binding_target(request.identity, request.user_id),
            tool_policy=tool_policy,  # type: ignore[arg-type]
            persona=persona,  # type: ignore[arg-type]
            recalled_memories=memories,  # type: ignore[arg-type]
            relationship_context=relationship_context,
            person_profile=person_profile,
            allowed_tools=allowed_tools,  # type: ignore[arg-type]
            initiative_bias=0.0,
        ),
        diagnostics={"preview_safe": True, "summary_source": "session_read"},
    )


def _build_preview_hard_rule_decision(
    *,
    identity: "ChatSessionIdentity",
    latest_user_turn: "ChatMessageDetailView | None",
    latest_user_message: str | None,
    user_id: str | None,
    now: datetime,
):
    """Evaluate preview-safe hard rules without touching session runtime state."""

    is_private = identity.scene_type == "private"
    direct_signal = _preview_direct_signal(
        identity=identity,
        latest_user_turn=latest_user_turn,
    )
    resolved_user_id = user_id or identity.subject_id or identity.scene_id
    message_text = latest_user_message or ""
    wake_context = WakeContext(
        bot_self_id=identity.bot_id,
        user_id=resolved_user_id,
        message_text=message_text,
        is_tome=direct_signal,
        is_private=is_private,
        is_future_task=False,
    )
    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text=message_text,
        source_message_id=(
            latest_user_turn.message_id if latest_user_turn is not None else None
        ),
        user_id=resolved_user_id,
        direct_signal=direct_signal,
        is_private=is_private,
        event_dedupe_key=(
            latest_user_turn.platform_message_id
            if latest_user_turn is not None
            else None
        ),
        event_dedupe_claimed=True,
    )
    return decide_runtime_hard_rule(
        wake_context=wake_context,
        source=source,
        session_runtime=None,
        now=now,
    )


def _build_preview_social_decision(
    *,
    hard_rule_decision: RuntimeHardRuleDecision,
    has_latest_user_message: bool,
) -> ReplyStrategyDecision | None:
    """Return a bounded no-model social-policy placeholder for preview."""

    if not has_latest_user_message:
        return None
    if not hard_rule_decision.should_reply:
        return ReplyStrategyDecision(
            action="silent",
            should_speak=False,
            tool_mode="avoid",
            reason_codes=("hard_rule_suppressed", *hard_rule_decision.reason_codes),
            reason_text=hard_rule_decision.reason_text,
            evidence={
                "policy_source": "preview",
                "hard_rule_action": hard_rule_decision.action,
            },
            decision_source="fallback",
        )
    return ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("preview_social_judgment_not_invoked",),
        reason_text="Preview does not call the social judgment model.",
        evidence={"policy_source": "preview", "preview_only": True},
        decision_source="fallback",
    )


def _build_preview_diagnostics(
    *,
    identity: "ChatSessionIdentity",
    latest_user_turn: "ChatMessageDetailView | None",
    hard_rule_decision: RuntimeHardRuleDecision,
    social_decision: ReplyStrategyDecision | None,
) -> tuple[str, ...]:
    diagnostics = [
        "social_judgment_model_not_invoked",
        "future_task_metadata_unavailable",
    ]
    if latest_user_turn is None:
        diagnostics.append("latest_user_message_unavailable")
    elif identity.scene_type == "group":
        diagnostics.append("live_platform_mention_assumed_from_persisted_message")
    if not hard_rule_decision.should_reply:
        diagnostics.extend(
            f"hard_rule_suppressed:{reason_code}"
            for reason_code in hard_rule_decision.reason_codes
        )
    if social_decision is not None and not social_decision.should_speak:
        diagnostics.extend(
            f"social_policy_suppressed:{reason_code}"
            for reason_code in social_decision.reason_codes
        )
    return tuple(dict.fromkeys(diagnostics))


def _suppressed_prompt_channels(
    *,
    mode: str,
    reason_text: str,
) -> AISessionPromptChannels:
    return AISessionPromptChannels(
        mode=mode,
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
        instruction=reason_text,
        sections=(
            AISessionPromptSection(
                role="system",
                name="Suppressed",
                content=reason_text,
            ),
        ),
    )


def _suppressed_prompt_diagnostics() -> AISessionPromptDiagnostics:
    return AISessionPromptDiagnostics(
        prompt_purpose="suppressed",
        stable_section_names=(),
        dynamic_section_names=(),
        stable_section_count=0,
        dynamic_section_count=0,
        total_section_count=0,
    )


def _build_preview_prompt_outputs(  # noqa: PLR0913
    *,
    request: AIRuntimeReplyRequest,
    inputs: ReplyInputs,
    prompt_planning: ReplyPromptPlanningInput,
    has_tools: bool,
    hard_rule_decision: RuntimeHardRuleDecision,
    social_decision: ReplyStrategyDecision | None,
) -> tuple[
    AISessionPromptChannels,
    AISessionPromptDiagnostics,
    AISessionPromptChannels | None,
    AISessionPromptDiagnostics | None,
    str,
    str | None,
]:
    planning_mode = "planner" if has_tools else "roleplay"
    should_show_prompt = hard_rule_decision.should_reply and (
        social_decision is not None and social_decision.should_speak
    )
    if should_show_prompt:
        assert social_decision is not None
        planning_packet = build_initial_reply_prompt_packet(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prompt_planning,
        )
        planning_channels, planning_prompt_diagnostics = (
            project_prompt_packet_to_preview(planning_packet, mode=planning_mode)
        )
        rendered_prompt = render_flat(planning_packet)
    else:
        suppression_text = (
            hard_rule_decision.reason_text
            if not hard_rule_decision.should_reply
            else "Suppressed by social policy before prompt generation."
        )
        planning_channels = _suppressed_prompt_channels(
            mode=planning_mode,
            reason_text=suppression_text,
        )
        planning_prompt_diagnostics = _suppressed_prompt_diagnostics()
        rendered_prompt = suppression_text

    compose_input = AIRuntimeComposeInput(
        persona=inputs.persona,
        scene_type=request.identity.scene_type,
        person_profile=inputs.person_profile,
        relationship=inputs.relationship_context,
        tool_policy=prompt_planning.skill_runtime.policy_text,
        tool_results=prompt_planning.skill_runtime.result_lines,
        memories=inputs.recalled_memories,
        conversation_summary=inputs.conversation_summary,
        social_policy_summary=(
            summarize_reply_strategy_decision(social_decision)
            if social_decision is not None
            else None
        ),
        turns=inputs.turns,
    )
    roleplay_packet = build_roleplay_reply_packet(compose_input)
    if has_tools and should_show_prompt:
        roleplay_channels, roleplay_prompt_diagnostics = (
            project_prompt_packet_to_preview(roleplay_packet, mode="roleplay")
        )
        rendered_roleplay_prompt = render_flat(roleplay_packet)
    else:
        roleplay_channels = None
        roleplay_prompt_diagnostics = None
        rendered_roleplay_prompt = None
    return (
        planning_channels,
        planning_prompt_diagnostics,
        roleplay_channels,
        roleplay_prompt_diagnostics,
        rendered_prompt,
        rendered_roleplay_prompt,
    )


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
    resolved_user_id = user_id or identity.scene_id
    request = _build_preview_request(
        identity=identity,
        latest_user_turn=latest_user_turn,
        latest_user_message=latest_user_message,
        user_id=resolved_user_id,
    )
    prompt_time = turns[-1].created_at if turns else datetime.now(timezone.utc)
    group_name = await _load_group_name(identity)
    relationship_target = build_relationship_target(identity, resolved_user_id)
    relationship_context = await load_relationship_context(
        target=relationship_target,
    )
    persona = await ai_persona_service.build_persona_prompt_bundle(
        target=build_persona_binding_target(identity, resolved_user_id),
        render_context=build_persona_render_context(
            bot_id=identity.bot_id,
            current_time=prompt_time,
            platform=identity.platform,
            scene_type=identity.scene_type,
            scene_id=identity.scene_id,
            session_id=identity.session_id,
            group_name=group_name,
            user_id=resolved_user_id,
            user_name=_find_recent_user_name(turns, resolved_user_id)
            or resolved_user_id,
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
            user_id=resolved_user_id,
        ),
    )
    memories = (
        await retrieve_memories_for_preview(
            identity=identity,
            user_id=resolved_user_id,
            query_text=latest_user_message or "",
        )
        if latest_user_message
        else []
    )
    tool_results = extract_tool_result_lines(turns)
    tool_policy_text = summarize_tool_policy(
        ai_tool_service.registry.list_tools(),
        tool_policy,
    )
    person_profile = await load_person_profile_for_prompt(
        identity=identity,
        user_id=resolved_user_id,
    )
    allowed_tools = ai_tool_service.list_allowed_tools(tool_policy)
    has_tools = bool(allowed_tools)
    pre_tool_task_class = select_pre_tool_reply_task_class(has_tools=has_tools)
    selected = await ai_model_facade.select_model(
        query=AIModelRouteQuery(task_class=pre_tool_task_class),
        target=build_model_binding_target(identity, resolved_user_id),
    )
    roleplay_selected = (
        await ai_model_facade.select_model(
            query=AIModelRouteQuery(task_class=select_post_tool_reply_task_class()),
            target=build_model_binding_target(identity, resolved_user_id),
        )
        if has_tools
        else None
    )
    context_turns = to_context_turns(turns)
    hard_rule_decision = _build_preview_hard_rule_decision(
        identity=identity,
        latest_user_turn=latest_user_turn,
        latest_user_message=latest_user_message,
        user_id=resolved_user_id,
        now=prompt_time,
    )
    social_decision = _build_preview_social_decision(
        hard_rule_decision=hard_rule_decision,
        has_latest_user_message=latest_user_message is not None,
    )
    preview_diagnostics = _build_preview_diagnostics(
        identity=identity,
        latest_user_turn=latest_user_turn,
        hard_rule_decision=hard_rule_decision,
        social_decision=social_decision,
    )
    context_bundle = _build_preview_context_bundle(
        request=request,
        turns=context_turns,
        conversation_summary=conversation.summary_text,
        relationship_target=relationship_target,
        tool_policy=tool_policy,
        persona=persona,
        memories=memories,
        relationship_context=relationship_context,
        person_profile=person_profile,
        allowed_tools=tuple(allowed_tools),
    )
    inputs = context_bundle.inputs
    prompt_planning = ReplyPromptPlanningInput(
        skill_runtime=ToolGatewayResult(
            policy_text=tool_policy_text,
            result_lines=tool_results,
            turns=(),
        ),
        skill_activation=None,
        has_tools=has_tools,
    )
    (
        planning_channels,
        planning_prompt_diagnostics,
        roleplay_channels,
        roleplay_prompt_diagnostics,
        rendered_prompt,
        rendered_roleplay_prompt,
    ) = _build_preview_prompt_outputs(
        request=request,
        inputs=inputs,
        prompt_planning=prompt_planning,
        has_tools=has_tools,
        hard_rule_decision=hard_rule_decision,
        social_decision=social_decision,
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
        hard_rule_action=hard_rule_decision.action,
        hard_rule_reason_text=hard_rule_decision.reason_text,
        hard_rule_reason_codes=hard_rule_decision.reason_codes,
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
        preview_diagnostics=preview_diagnostics,
        tool_results=tool_results,
        memories=tuple(memories),
        operator_memory_count=operator_memory_count,
        summary_memory_count=summary_memory_count,
        long_term_memory_count=long_term_memory_count,
        knowledge_memory_count=knowledge_memory_count,
        planning_prompt_diagnostics=planning_prompt_diagnostics,
        roleplay_prompt_diagnostics=roleplay_prompt_diagnostics,
        planning_channels=planning_channels,
        roleplay_channels=roleplay_channels,
        rendered_roleplay_prompt=rendered_roleplay_prompt,
        rendered_prompt=rendered_prompt,
    )


__all__ = ["build_scene_prompt_preview"]
