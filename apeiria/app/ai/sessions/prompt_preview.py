"""Prompt-preview assembly for AI session workbench reads."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.access.groups import group_service
from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.model import AIModelRouteQuery
from apeiria.ai.model.routing.profile import ai_model_profile_service
from apeiria.ai.persona import (
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
from apeiria.app.ai.diagnostics.workbench import (
    extract_tool_result_lines,
    select_latest_user_turn,
    to_context_turns,
)
from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.runtime.context.memories import retrieve_memories_for_preview
from apeiria.app.ai.runtime.context.person_profiles import (
    load_person_profile_for_prompt,
)
from apeiria.app.ai.runtime.context.personas import (
    build_model_binding_target,
    build_persona_binding_target,
)
from apeiria.app.ai.runtime.context.projection import (
    project_runtime_context,
)
from apeiria.app.ai.runtime.context.relationships import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.planning.hard_rules import decide_runtime_hard_rule
from apeiria.app.ai.runtime.planning.prompts import (
    build_pre_tool_reply_packet,
    build_roleplay_reply_packet,
    compose_input_from_context_projection,
)
from apeiria.app.ai.runtime.planning.reply_decision import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.runtime.planning.tool_exposure import (
    ToolOrchestrator,
    build_tool_guidance_text,
    compile_tool_exposure_provider_schema,
)
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.app.ai.runtime.session.management import (
    managed_session_diagnostics,
    managed_session_disabled_decision,
)
from apeiria.app.ai.runtime.stages import RuntimeContextBundle
from apeiria.conversation.service import chat_session_service

from .models import (
    AISessionPromptChannels,
    AISessionPromptDiagnostics,
    AISessionPromptPreview,
    AISessionPromptSection,
)
from .prompt_projection import project_prompt_packet_to_preview
from .repository import AISessionManagementRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AISelectedModel
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolDefinition, AIToolPolicy
    from apeiria.app.ai.runtime.context.projection import RuntimeContextProjection
    from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
    from apeiria.conversation.models import (
        ChatContextMessageView,
        ChatMessageDetailView,
        ChatSessionAdminView,
        ChatSessionIdentity,
    )


@dataclass(frozen=True, slots=True)
class PromptPreviewPromptOutputs:
    """Packet-projected prompt outputs for one preview read."""

    planning_channels: AISessionPromptChannels
    planning_prompt_diagnostics: AISessionPromptDiagnostics
    roleplay_channels: AISessionPromptChannels | None
    roleplay_prompt_diagnostics: AISessionPromptDiagnostics | None
    rendered_prompt: str
    rendered_roleplay_prompt: str | None


@dataclass(frozen=True, slots=True)
class PromptPreviewReadResult:
    """Runtime-owned read result used to render a session prompt preview."""

    turn: RuntimeTurnInput
    context: RuntimeContextMaterials
    hard_rule_decision: RuntimeHardRuleDecision
    social_decision: ReplyStrategyDecision | None
    preview_diagnostics: tuple[str, ...]
    prompt_outputs: PromptPreviewPromptOutputs
    selected: "AISelectedModel | None"
    roleplay_selected: "AISelectedModel | None"
    pre_tool_task_class: str
    has_tools: bool
    persona: "ReplyPersonaPromptBundleLike | None"
    conversation_summary: str | None
    relationship_context: str | None
    tool_policy_text: str
    tool_results: tuple[str, ...]
    memories: tuple["AIMemoryDefinition", ...]


def _find_recent_user_name(
    turns: "Sequence[ChatContextMessageView | ChatMessageDetailView]",
    user_id: str,
) -> str | None:
    for turn in reversed(turns):
        if getattr(turn, "turn_disposition", None) == "observed":
            continue
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
    if latest_user_turn is not None and latest_user_turn.turn_disposition == "observed":
        return False
    return identity.scene_type == "private" or bool(
        latest_user_turn is not None
        and (latest_user_turn.directed_to_bot or latest_user_turn.mentions_bot)
    )


def _build_preview_turn(
    *,
    identity: "ChatSessionIdentity",
    latest_user_turn: "ChatMessageDetailView | None",
    latest_user_message: str | None,
    user_id: str,
) -> RuntimeTurnInput:
    """Normalize preview inputs into a runtime-owned turn input."""

    return RuntimeTurnInput(
        identity=identity,
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text=latest_user_message or "",
            source_message_id=(
                latest_user_turn.message_id if latest_user_turn is not None else None
            ),
            user_id=user_id,
            direct_signal=_preview_direct_signal(
                identity=identity,
                latest_user_turn=latest_user_turn,
            ),
            is_private=identity.scene_type == "private",
            event_dedupe_key=(
                latest_user_turn.platform_message_id
                if latest_user_turn is not None
                else None
            ),
            event_dedupe_claimed=True,
        ),
        sender_id=identity.bot_id,
    )


def _build_preview_context_bundle(  # noqa: PLR0913
    *,
    turn: RuntimeTurnInput,
    turns: list["ChatContextMessageView"],
    conversation_summary: str | None,
    relationship_target: "AIRelationshipTarget",
    tool_policy: "AIToolPolicy",
    persona: "ReplyPersonaPromptBundleLike | None",
    memories: "Sequence[AIMemoryDefinition]",
    relationship_context: str | None,
    person_profile: tuple[str, ...],
    allowed_tools: "Sequence[AIToolDefinition]",
) -> RuntimeContextBundle:
    """Build preview-safe context without mutating runtime state."""

    return RuntimeContextBundle(
        stage="context",
        context=RuntimeContextMaterials(
            turns=turns,
            conversation_summary=conversation_summary,
            relationship_target=relationship_target,
            model_target=build_model_binding_target(turn.identity, turn.user_id),
            tool_policy=tool_policy,
            persona=persona,
            recalled_memories=list(memories),
            relationship_context=relationship_context,
            person_profile=person_profile,
            allowed_tools=tuple(allowed_tools),
            initiative_bias=0.0,
        ),
        diagnostics={"preview_safe": True, "summary_source": "sessions"},
    )


def _build_preview_hard_rule_decision(
    *,
    turn: RuntimeTurnInput,
    now: datetime,
):
    """Evaluate preview-safe hard rules without touching session runtime state."""

    managed_session = AISessionManagementRepository().get_session_sync(
        turn.identity.session_id,
    )
    if managed_session is not None:
        disabled_decision = managed_session_disabled_decision(managed_session)
        if disabled_decision is not None:
            return disabled_decision

    wake_context = WakeContext(
        bot_self_id=turn.sender_id,
        user_id=turn.user_id,
        message_text=turn.message_text,
        is_tome=turn.is_tome,
        is_private=turn.source.is_private,
        is_future_task=False,
    )
    return decide_runtime_hard_rule(
        wake_context=wake_context,
        source=turn.source,
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
    managed_session = AISessionManagementRepository().get_session_sync(
        identity.session_id,
    )
    diagnostics = [
        "social_judgment_model_not_invoked",
        "future_task_metadata_unavailable",
        *managed_session_diagnostics(managed_session),
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


def _project_preview_context(
    *,
    turn: RuntimeTurnInput,
    context: RuntimeContextMaterials,
    tool_runtime: RuntimeToolLoopResult,
    skill_activation: str | None,
    social_decision: ReplyStrategyDecision | None,
) -> "RuntimeContextProjection":
    return project_runtime_context(
        turn=turn,
        context=context,
        social_decision=social_decision,
        tool_runtime=tool_runtime,
        skill_activation=skill_activation,
        projection_mode="preview",
    )


def _build_preview_prompt_outputs(
    *,
    context_projection: "RuntimeContextProjection",
    has_tools: bool,
    tool_guidance: str | None,
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
    compose_input = compose_input_from_context_projection(context_projection.prompt)
    compose_input = replace(compose_input, tool_guidance=tool_guidance)
    if should_show_prompt:
        assert social_decision is not None
        planning_packet = build_pre_tool_reply_packet(
            compose_input,
            has_tools=has_tools,
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


class PromptPreviewReader:
    """Non-mutating reader for prompt preview assembly."""

    async def build(
        self,
        *,
        conversation: "ChatSessionAdminView",
        identity: "ChatSessionIdentity",
        turns: list["ChatMessageDetailView"],
    ) -> PromptPreviewReadResult:
        latest_user_turn = select_latest_user_turn(turns)
        latest_user_message = (
            latest_user_turn.text_content.strip()
            if latest_user_turn is not None
            else None
        )
        user_id = identity.subject_id or (
            latest_user_turn.author_id if latest_user_turn is not None else None
        )
        resolved_user_id = user_id or identity.scene_id
        preview_turn = _build_preview_turn(
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
        context_turns = to_context_turns(turns)
        hard_rule_decision = _build_preview_hard_rule_decision(
            turn=preview_turn,
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
            turn=preview_turn,
            turns=context_turns,
            conversation_summary=conversation.summary_text,
            relationship_target=relationship_target,
            tool_policy=tool_policy,
            persona=persona,
            memories=memories,
            relationship_context=relationship_context,
            person_profile=person_profile,
            allowed_tools=tuple(ai_tool_service.list_allowed_tools(tool_policy)),
        )
        context = context_bundle.context
        allowed_tool_specs = (
            ()
            if social_decision is not None and social_decision.tool_mode == "avoid"
            else tuple(context.allowed_tools)
        )
        tool_orchestrator = ToolOrchestrator()
        initial_exposure_plan = tool_orchestrator.plan_exposure(
            allowed_tools=allowed_tool_specs,
            policy=context.tool_policy,
            ordinary_ambient_group=(
                identity.scene_type == "group" and not preview_turn.is_tome
            ),
            execution_timeout_seconds=get_ai_plugin_config().tool_execution_timeout_seconds,
        )
        has_tools = initial_exposure_plan.has_executable_tools
        pre_tool_task_class = select_pre_tool_reply_task_class(has_tools=has_tools)
        selected = await ai_model_profile_service.select_model(
            query=AIModelRouteQuery(task_class=pre_tool_task_class),
            target=build_model_binding_target(identity, resolved_user_id),
        )
        preview_exposure_plan = tool_orchestrator.plan_exposure(
            allowed_tools=allowed_tool_specs,
            policy=context.tool_policy,
            ordinary_ambient_group=(
                identity.scene_type == "group" and not preview_turn.is_tome
            ),
            execution_timeout_seconds=get_ai_plugin_config().tool_execution_timeout_seconds,
            model_supports_tools=(
                selected.resolved_capabilities.supports_tool_calling
                if selected is not None
                else False
            ),
        )
        has_tools = preview_exposure_plan.has_executable_tools
        pre_tool_task_class = select_pre_tool_reply_task_class(has_tools=has_tools)
        roleplay_selected = (
            await ai_model_profile_service.select_model(
                query=AIModelRouteQuery(task_class=select_post_tool_reply_task_class()),
                target=build_model_binding_target(identity, resolved_user_id),
            )
            if has_tools
            else None
        )
        tool_runtime = RuntimeToolLoopResult(
            policy_text=tool_policy_text,
            result_lines=tool_results,
            turns=(),
            available_tools=compile_tool_exposure_provider_schema(
                preview_exposure_plan,
                current_time=prompt_time,
            ),
            diagnostics=dict(preview_exposure_plan.diagnostics),
        )
        projected_context = _project_preview_context(
            turn=preview_turn,
            context=context,
            tool_runtime=tool_runtime,
            skill_activation=None,
            social_decision=social_decision,
        )
        (
            planning_channels,
            planning_prompt_diagnostics,
            roleplay_channels,
            roleplay_prompt_diagnostics,
            rendered_prompt,
            rendered_roleplay_prompt,
        ) = _build_preview_prompt_outputs(
            context_projection=projected_context,
            has_tools=has_tools,
            tool_guidance=build_tool_guidance_text(preview_exposure_plan),
            hard_rule_decision=hard_rule_decision,
            social_decision=social_decision,
        )
        return PromptPreviewReadResult(
            turn=preview_turn,
            context=context,
            hard_rule_decision=hard_rule_decision,
            social_decision=social_decision,
            preview_diagnostics=preview_diagnostics,
            prompt_outputs=PromptPreviewPromptOutputs(
                planning_channels=planning_channels,
                planning_prompt_diagnostics=planning_prompt_diagnostics,
                roleplay_channels=roleplay_channels,
                roleplay_prompt_diagnostics=roleplay_prompt_diagnostics,
                rendered_prompt=rendered_prompt,
                rendered_roleplay_prompt=rendered_roleplay_prompt,
            ),
            selected=selected,
            roleplay_selected=roleplay_selected,
            pre_tool_task_class=pre_tool_task_class,
            has_tools=has_tools,
            persona=projected_context.preview.persona,
            conversation_summary=projected_context.preview.conversation_summary,
            relationship_context=projected_context.preview.relationship_context,
            tool_policy_text=projected_context.preview.tool_policy_text,
            tool_results=projected_context.preview.tool_results,
            memories=projected_context.preview.memories,
        )


async def build_scene_prompt_preview(
    *,
    scene_id: str,
    turn_limit: int = 50,
) -> AISessionPromptPreview | None:
    ensure_ai_runtime_support_initialized(source="admin_fallback")
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
    preview = await PromptPreviewReader().build(
        conversation=conversation,
        identity=identity,
        turns=turns,
    )
    hard_rule_decision = preview.hard_rule_decision
    social_decision = preview.social_decision
    selected = preview.selected
    roleplay_selected = preview.roleplay_selected
    persona = preview.persona
    memories = preview.memories
    prompt_outputs = preview.prompt_outputs
    return AISessionPromptPreview(
        session_id=scene_id,
        latest_user_message=preview.turn.message_text or None,
        planning_source_id=selected.source.source_id if selected is not None else None,
        planning_profile_id=(
            selected.profile.profile_id if selected is not None else None
        ),
        planning_model_name=(
            selected.resolved_model_name if selected is not None else None
        ),
        planning_task_class=preview.pre_tool_task_class,
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
            select_post_tool_reply_task_class() if preview.has_tools else None
        ),
        source_id=selected.source.source_id if selected is not None else None,
        profile_id=selected.profile.profile_id if selected is not None else None,
        model_name=selected.resolved_model_name if selected is not None else None,
        persona_id=persona.persona_id if persona is not None else None,
        conversation_summary=preview.conversation_summary,
        relationship_context=preview.relationship_context,
        tool_policy=preview.tool_policy_text,
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
        preview_diagnostics=preview.preview_diagnostics,
        tool_results=preview.tool_results,
        memories=tuple(memories),
        operator_memory_count=_memory_count(memories, layer="operator"),
        summary_memory_count=_memory_count(memories, layer="summary"),
        long_term_memory_count=_memory_count(memories, layer="long_term"),
        knowledge_memory_count=_memory_count(memories, layer="knowledge"),
        planning_prompt_diagnostics=prompt_outputs.planning_prompt_diagnostics,
        roleplay_prompt_diagnostics=prompt_outputs.roleplay_prompt_diagnostics,
        planning_channels=prompt_outputs.planning_channels,
        roleplay_channels=prompt_outputs.roleplay_channels,
        rendered_roleplay_prompt=prompt_outputs.rendered_roleplay_prompt,
        rendered_prompt=prompt_outputs.rendered_prompt,
    )


def _memory_count(
    memories: "Sequence[AIMemoryDefinition]",
    *,
    layer: str,
) -> int:
    return sum(1 for memory in memories if memory.memory_layer == layer)


__all__ = ["build_scene_prompt_preview"]
