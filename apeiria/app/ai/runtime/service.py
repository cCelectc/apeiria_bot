"""Runtime service entrypoint for AI message handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from nonebot.log import logger
from nonebot_plugin_orm import get_session

from apeiria.app.ai.conversation.service import ChatMessageCreate, chat_session_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.persona.models import AIPersonaBindingTarget
from apeiria.app.ai.persona.service import (
    ai_persona_service,
    build_persona_render_context,
)
from apeiria.app.ai.relationship.service import ai_relationship_service
from apeiria.app.ai.reply_strategy import (
    ReplyStrategyDecision,
    build_wake_context,
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
    reply_strategy_service,
    summarize_reply_strategy_decision,
)
from apeiria.app.ai.reply_strategy.models import WakeContext
from apeiria.app.ai.runtime.composer import (
    AIRuntimeComposeInput,
    compose_pre_tool_reply_prompt,
    compose_roleplay_reply_prompt,
)
from apeiria.app.ai.runtime.memory_steps import (
    load_person_profile_for_prompt,
    recall_memories,
    store_extracted_memories,
)
from apeiria.app.ai.runtime.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
    update_relationship_state,
)
from apeiria.app.ai.runtime.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.tools.policy import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
)
from apeiria.app.ai.tools.runtime import AIToolRuntimeRequest, ai_tool_runtime
from apeiria.app.ai.tools.service import ai_tool_service
from apeiria.app.groups import group_service
from apeiria.app.message_delivery import (
    MessageDeliveryRequest,
    MessageDeliveryResult,
    MessageDeliveryTarget,
    message_delivery_service,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import (
        ChatContextMessageView,
        ChatSessionIdentity,
    )
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.memory.models import AIMemoryDefinition, AIMessageSentiment
    from apeiria.app.ai.model.adapter import (
        AIModelGenerateResponse,
        AIModelToolDefinition,
    )
    from apeiria.app.ai.model.selection import AISelectedModel
    from apeiria.app.ai.persona.service import AIPersonaRenderContext
    from apeiria.app.ai.runtime.prompting import AIPersonaPromptBundleLike
    from apeiria.app.ai.tools.models import (
        AIToolPolicy,
        AIToolTurnCreateInput,
    )
    from apeiria.app.ai.tools.runtime import AIToolRuntimeResult


@dataclass(frozen=True)
class AIRuntimeReplyRequest:
    """Normalized runtime request shared by message and future-task entrypoints."""

    identity: "ChatSessionIdentity"
    message_text: str
    source_message_id: str | None
    user_id: str
    sender_id: str
    runtime_mode: Literal["message", "future_task"]
    is_tome: bool = False
    future_task: "AIFutureTaskDefinition | None" = None
    sentiment: "AIMessageSentiment | None" = None


@dataclass(frozen=True)
class AIRuntimeReplyResult:
    """Final runtime reply plus optional outbound delivery metadata."""

    reply_text: str
    delivery_result: MessageDeliveryResult | None = None


@dataclass(frozen=True)
class AIRuntimeGenerationRequest:
    """One model generation request with trace metadata."""

    selected: "AISelectedModel"
    prompt: str
    trace_id: str
    session_id: str
    tools: tuple["AIModelToolDefinition", ...]
    failure_stage: str


@dataclass(frozen=True)
class AIRuntimeReplyState:
    """Shared state needed for reply generation with tool execution."""

    request: AIRuntimeReplyRequest
    selected: "AISelectedModel"
    skill_runtime: "AIToolRuntimeResult"
    recalled_memories: list["AIMemoryDefinition"]
    person_profile: tuple[str, ...]
    relationship_context: str | None
    conversation_summary: str | None
    persona: "AIPersonaPromptBundleLike | None"
    turns: list["ChatContextMessageView"]
    tool_policy: "AIToolPolicy"
    social_decision: ReplyStrategyDecision
    current_time: datetime
    trace_id: str


def _to_persona_target(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> AIPersonaBindingTarget:
    return AIPersonaBindingTarget(
        conversation_id=identity.session_id,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
        user_id=identity.subject_id or user_id,
    )


def _to_model_target(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> AIModelBindingTarget:
    return AIModelBindingTarget(
        conversation_id=identity.session_id,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
        user_id=identity.subject_id or user_id,
    )


async def _resolve_tool_policy(
    session: "AsyncSession",
    identity: "ChatSessionIdentity",
    *,
    is_tome: bool,
) -> "AIToolPolicy":
    return await ai_tool_policy_binding_service.resolve_scene_policy(
        session,
        scene_context=AIToolSceneContext(
            scope_type=identity.scene_type,
            is_tome=is_tome,
        ),
        target=AIToolPolicyBindingTarget(
            conversation_id=identity.session_id,
            group_id=identity.scene_id if identity.scene_type == "group" else None,
            user_id=identity.subject_id,
        ),
    )


async def _append_tool_observation_turns(
    session: "AsyncSession",
    *,
    identity: "ChatSessionIdentity",
    trace_id: str,
    tool_turns: tuple["AIToolTurnCreateInput", ...],
) -> None:
    for index, turn in enumerate(tool_turns):
        await chat_session_service.append_message(
            session,
            identity,
            ChatMessageCreate(
                author_role="tool",
                author_id=turn.author_id,
                text_content=turn.text_content,
                message_kind="tool",
                meta={
                    "trace_id": trace_id,
                    "index": index,
                    **turn.meta,
                },
            ),
        )


def _build_future_task_context(task: "AIFutureTaskDefinition | None") -> str | None:
    if task is None:
        return None
    return "\n".join(
        (
            f"task_id={task.task_id}",
            f"title={task.title}",
            f"description={task.description}",
            f"trigger_at={task.trigger_at.isoformat()}",
            f"status={task.status}",
        )
    )


def _find_recent_user_name(
    turns: list["ChatContextMessageView"],
    user_id: str,
) -> str | None:
    for turn in reversed(turns):
        if turn.author_role != "user" or turn.author_id != user_id:
            continue
        author_name = (turn.author_name or "").strip()
        if author_name:
            return author_name
    return None


async def _build_persona_render_context(
    request: AIRuntimeReplyRequest,
    *,
    current_time: datetime,
    turns: list["ChatContextMessageView"],
) -> "AIPersonaRenderContext":
    identity = request.identity
    group_name = await _load_group_name(identity)
    return build_persona_render_context(
        bot_id=identity.bot_id,
        current_time=current_time,
        platform=identity.platform,
        scene_type=identity.scene_type,
        scene_id=identity.scene_id,
        session_id=identity.session_id,
        group_name=group_name,
        user_id=request.user_id,
        user_name=_find_recent_user_name(turns, request.user_id) or request.user_id,
    )


async def _load_group_name(identity: "ChatSessionIdentity") -> str | None:
    if identity.scene_type != "group":
        return None
    group = await group_service.get_group(identity.scene_id)
    return group.group_name if group is not None else None


def _should_skip_generation(decision: ReplyStrategyDecision) -> bool:
    return not decision.should_speak


class AIRuntimeService:
    """Minimal end-to-end runtime path for the AI plugin."""

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        wake_context = build_wake_context(bot, event)
        if wake_context is None:
            return None
        message_text = wake_context.message_text

        async with get_session() as session:
            ingested = await chat_session_service.ingest_event(session, bot, event)
            if ingested is None:
                return None

            identity, turn = ingested
            user_id = str(event.get_user_id())
            is_tome = bool(hasattr(event, "is_tome") and event.is_tome())
            extraction_result = await store_extracted_memories(
                session,
                identity=identity,
                user_id=user_id,
                message_text=message_text,
                source_message_id=turn.message_id,
            )
            result = await self._run_reply_pipeline(
                session,
                trace_id=f"ai_trace_{uuid4().hex}",
                request=AIRuntimeReplyRequest(
                    identity=identity,
                    message_text=message_text,
                    source_message_id=turn.message_id,
                    user_id=user_id,
                    sender_id=str(bot.self_id),
                    runtime_mode="message",
                    is_tome=is_tome,
                    sentiment=extraction_result.sentiment,
                ),
                wake_context=wake_context,
            )
            return result.reply_text if result is not None else None

    async def handle_future_task(
        self,
        task_id: str,
    ) -> AIRuntimeReplyResult | None:
        """Handle one due future task by running the normal reply pipeline."""

        async with get_session() as session:
            task = await ai_future_task_service.get_task(session, task_id=task_id)
            if task is None or task.status != "running":
                return None

            identity = await chat_session_service.get_session_identity(
                session,
                session_id=task.session_id,
            )
            if identity is None:
                return None

            user_id = identity.subject_id or task.user_id or identity.scene_id
            return await self._run_reply_pipeline(
                session,
                trace_id=f"ai_trace_{uuid4().hex}",
                request=AIRuntimeReplyRequest(
                    identity=identity,
                    message_text=task.description,
                    source_message_id=task.source_message_id,
                    user_id=user_id,
                    sender_id=identity.bot_id,
                    runtime_mode="future_task",
                    future_task=task,
                ),
            )

    async def _run_reply_pipeline(
        self,
        session: "AsyncSession",
        *,
        trace_id: str,
        request: AIRuntimeReplyRequest,
        wake_context: WakeContext | None = None,
    ) -> AIRuntimeReplyResult | None:
        current_time = datetime.now(timezone.utc)
        identity = request.identity
        turns = await chat_session_service.list_recent_messages(
            session,
            identity,
            max_messages=8,
        )
        conversation_summary = await chat_session_service.update_summary_text(
            session,
            identity,
            messages=turns,
        )
        relationship_target = build_relationship_target(identity, request.user_id)
        persona_target = _to_persona_target(identity, request.user_id)
        model_target = _to_model_target(identity, request.user_id)
        tool_policy = await _resolve_tool_policy(
            session,
            identity,
            is_tome=request.is_tome,
        )
        persona = await ai_persona_service.build_persona_prompt_bundle(
            session,
            target=persona_target,
            render_context=await _build_persona_render_context(
                request,
                current_time=current_time,
                turns=turns,
            ),
        )
        if request.runtime_mode == "message" and request.sentiment is not None:
            await update_relationship_state(
                session,
                target=relationship_target,
                sentiment=request.sentiment,
                is_tome=request.is_tome,
            )
        recalled_memories = await recall_memories(
            session,
            identity=identity,
            user_id=request.user_id,
            query_text=request.message_text,
        )
        relationship_context = await load_relationship_context(
            session,
            target=relationship_target,
        )
        person_profile = await load_person_profile_for_prompt(
            session,
            identity=identity,
            user_id=request.user_id,
        )
        allowed_tools = ai_tool_service.list_allowed_tools(tool_policy)

        # --- Resolve initiative_bias from relationship projection ---
        projection = await ai_relationship_service.project_state(
            session,
            platform=relationship_target.platform,
            group_id=relationship_target.group_id,
            user_id=relationship_target.user_id,
        )
        initiative_bias = projection.initiative_bias

        # --- Unified reply strategy pipeline ---
        if wake_context is None:
            wake_context = WakeContext(
                bot_self_id=request.sender_id,
                user_id=request.user_id,
                message_text=request.message_text,
                is_tome=request.is_tome,
                is_private=identity.scene_type == "private",
                is_future_task=request.runtime_mode == "future_task",
            )
        social_decision = await reply_strategy_service.evaluate(
            session,
            wake_context=wake_context,
            session_id=identity.session_id,
            scene_type=identity.scene_type,
            message_text=request.message_text,
            latest_user_turn_text=latest_user_turn_text(turns),
            conversation_summary=conversation_summary,
            relationship_context=relationship_context,
            persona_id=persona.persona_id if persona is not None else None,
            available_tool_names=tuple(tool.name for tool in allowed_tools),
            recent_turn_count=len(turns),
            recent_bot_turn_count=count_recent_bot_turns(turns),
            last_bot_turn_at=latest_bot_turn_at(turns),
            current_time=current_time,
            runtime_mode=request.runtime_mode,
            initiative_bias=initiative_bias,
            target=model_target,
        )
        if _should_skip_generation(social_decision):
            logger.info(
                "AI trace {} suppressed {} reply for session {} action={} reasons={}",
                trace_id,
                request.runtime_mode,
                identity.session_id,
                social_decision.action,
                ",".join(social_decision.reason_codes),
            )
            await session.commit()
            return None
        skill_runtime = await ai_tool_runtime.run_for_message(
            session,
            AIToolRuntimeRequest(
                session_id=identity.session_id,
                source_message_id=request.source_message_id,
                message_text=request.message_text,
                policy=tool_policy,
                recalled_memories=tuple(recalled_memories),
                relationship_context=relationship_context,
                current_time=current_time,
                tool_mode=social_decision.tool_mode,
            ),
        )
        pre_tool_task_class = select_pre_tool_reply_task_class(
            has_tools=bool(skill_runtime.available_tools),
        )
        selected = await ai_model_facade.select_model(
            session,
            query=AIModelRouteQuery(task_class=pre_tool_task_class),
            target=model_target,
        )
        await session.commit()
        if selected is None:
            logger.debug(
                "AI trace {} skipped reply: no model selected for session {}",
                trace_id,
                identity.session_id,
            )
            return None

        (
            response,
            skill_runtime,
            post_tool_task_class,
            delivery_result,
        ) = await self._generate_reply_with_tools(
            session,
            AIRuntimeReplyState(
                request=request,
                selected=selected,
                skill_runtime=skill_runtime,
                recalled_memories=recalled_memories,
                person_profile=person_profile,
                relationship_context=relationship_context,
                conversation_summary=conversation_summary,
                persona=persona,
                turns=turns,
                tool_policy=tool_policy,
                social_decision=social_decision,
                current_time=current_time,
                trace_id=trace_id,
            ),
        )
        if response is None or not response.content.strip():
            logger.debug(
                "AI trace {} skipped reply: empty model response for session {}",
                trace_id,
                identity.session_id,
            )
            return None

        await chat_session_service.append_message(
            session,
            identity,
            ChatMessageCreate(
                author_role="assistant",
                author_id=request.sender_id,
                text_content=response.content.strip(),
                meta={
                    "trace_id": trace_id,
                    "source_id": response.source_id,
                    "model_name": response.model_name,
                    "task_class": (
                        post_tool_task_class
                        if skill_runtime.turns
                        else pre_tool_task_class
                    ),
                    "recalled_memory_count": len(recalled_memories),
                    "tool_observation_count": len(skill_runtime.turns),
                    "social_action": social_decision.action,
                    "social_tool_mode": social_decision.tool_mode,
                    "social_reason_text": social_decision.reason_text,
                    "social_reason_codes": list(social_decision.reason_codes),
                    "social_policy_source": social_decision.evidence.get(
                        "policy_source"
                    ),
                    "runtime_mode": request.runtime_mode,
                    "future_task_id": (
                        request.future_task.task_id if request.future_task else None
                    ),
                    "future_task_status": (
                        request.future_task.status if request.future_task else None
                    ),
                    "delivery_channel": (
                        delivery_result.channel if delivery_result else None
                    ),
                    "delivery_delivered": (
                        delivery_result.delivered if delivery_result else None
                    ),
                    "delivery_error": (
                        delivery_result.error if delivery_result else None
                    ),
                    "delivery_remote_message_id": (
                        delivery_result.remote_message_id if delivery_result else None
                    ),
                },
            ),
        )
        turns_after = await chat_session_service.list_recent_messages(
            session,
            identity,
            max_messages=8,
        )
        await chat_session_service.update_summary_text(
            session,
            identity,
            messages=turns_after,
        )
        await session.commit()
        # Only count as "replied" when the reply was actually delivered.
        # For regular messages delivery_result is None (plugin handler sends).
        # For future_tasks delivery happens internally and may fail.
        if delivery_result is None or delivery_result.delivered:
            reply_strategy_service.notify_replied(identity.session_id)
        logger.info(
            "AI trace {} generated {} reply for session {} with source={} "
            "model={} memories={} tool_observations={}",
            trace_id,
            request.runtime_mode,
            identity.session_id,
            response.source_id,
            response.model_name,
            len(recalled_memories),
            len(skill_runtime.turns),
        )
        return AIRuntimeReplyResult(
            reply_text=response.content.strip(),
            delivery_result=delivery_result,
        )

    async def _generate_reply_with_tools(
        self,
        session: "AsyncSession",
        state: AIRuntimeReplyState,
    ) -> tuple[
        "AIModelGenerateResponse | None",
        "AIToolRuntimeResult",
        str | None,
        MessageDeliveryResult | None,
    ]:
        skill_runtime = state.skill_runtime
        has_tools = bool(skill_runtime.available_tools)
        response = await self._safe_generate(
            AIRuntimeGenerationRequest(
                selected=state.selected,
                prompt=compose_pre_tool_reply_prompt(
                    AIRuntimeComposeInput(
                        persona=state.persona,
                        scene_type=state.request.identity.scene_type,
                        person_profile=state.person_profile,
                        relationship=state.relationship_context,
                        tool_policy=skill_runtime.policy_text,
                        tool_results=skill_runtime.result_lines,
                        memories=state.recalled_memories,
                        conversation_summary=state.conversation_summary,
                        social_policy_summary=summarize_reply_strategy_decision(
                            state.social_decision
                        ),
                        future_task_context=_build_future_task_context(
                            state.request.future_task
                        ),
                        turns=state.turns,
                    ),
                    has_tools=has_tools,
                ),
                trace_id=state.trace_id,
                session_id=state.request.identity.session_id,
                tools=skill_runtime.available_tools,
                failure_stage="reply generation failed",
            )
        )
        if response is None:
            return None, state.skill_runtime, None, None

        post_tool_task_class = None
        if response.tool_calls:
            skill_runtime = await ai_tool_runtime.execute_tool_calls(
                session,
                AIToolRuntimeRequest(
                    session_id=state.request.identity.session_id,
                    source_message_id=state.request.source_message_id,
                    message_text=state.request.message_text,
                    policy=state.tool_policy,
                    recalled_memories=tuple(state.recalled_memories),
                    relationship_context=state.relationship_context,
                    current_time=state.current_time,
                    tool_mode=state.social_decision.tool_mode,
                ),
                tool_calls=response.tool_calls,
            )
            await _append_tool_observation_turns(
                session,
                identity=state.request.identity,
                trace_id=state.trace_id,
                tool_turns=skill_runtime.turns,
            )
            await session.commit()
            post_tool_task_class = select_post_tool_reply_task_class()
            roleplay_selected = await ai_model_facade.select_model(
                session,
                query=AIModelRouteQuery(task_class=post_tool_task_class),
                target=_to_model_target(
                    state.request.identity,
                    state.request.user_id,
                ),
            )
            response = await self._safe_generate(
                AIRuntimeGenerationRequest(
                    selected=roleplay_selected or state.selected,
                    prompt=compose_roleplay_reply_prompt(
                        AIRuntimeComposeInput(
                            persona=state.persona,
                            scene_type=state.request.identity.scene_type,
                            person_profile=state.person_profile,
                            relationship=state.relationship_context,
                            tool_policy=skill_runtime.policy_text,
                            tool_results=skill_runtime.result_lines,
                            memories=state.recalled_memories,
                            conversation_summary=state.conversation_summary,
                            social_policy_summary=summarize_reply_strategy_decision(
                                state.social_decision
                            ),
                            future_task_context=_build_future_task_context(
                                state.request.future_task
                            ),
                            turns=state.turns,
                        )
                    ),
                    trace_id=state.trace_id,
                    session_id=state.request.identity.session_id,
                    tools=(),
                    failure_stage="reply generation failed after tool calls",
                )
            )
        if response is None:
            return None, skill_runtime, post_tool_task_class, None
        delivery_result = await self._deliver_generated_reply(
            state.request,
            response.content.strip() if response.content else "",
        )
        return response, skill_runtime, post_tool_task_class, delivery_result

    async def _deliver_generated_reply(
        self,
        request: AIRuntimeReplyRequest,
        reply_text: str,
    ) -> MessageDeliveryResult | None:
        if request.runtime_mode != "future_task" or not reply_text.strip():
            return None
        return await message_delivery_service.send(
            MessageDeliveryRequest(
                target=MessageDeliveryTarget(
                    platform=request.identity.platform,
                    bot_id=request.identity.bot_id,
                    scope_type=request.identity.scene_type,
                    scope_id=request.identity.scene_id,
                    user_id=request.identity.subject_id or request.user_id,
                ),
                content_text=reply_text,
            )
        )

    async def _safe_generate(
        self,
        request: AIRuntimeGenerationRequest,
    ) -> "AIModelGenerateResponse | None":
        try:
            return await ai_model_facade.generate_text(
                request.selected,
                prompt=request.prompt,
                tools=request.tools,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace {} {} for session {}",
                request.trace_id,
                request.failure_stage,
                request.session_id,
            )
            return None


ai_runtime_service = AIRuntimeService()

__all__ = ["AIRuntimeService", "ai_runtime_service"]
