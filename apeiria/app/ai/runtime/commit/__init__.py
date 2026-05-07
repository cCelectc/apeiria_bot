"""Runtime commit stage for generated AI turns."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol, cast

from nonebot.log import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from datetime import datetime

    from apeiria.ai.model import AIModelGenerateResponse
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.app.ai.runtime.stages import (
        RuntimeCommitInput,
        RuntimeCommitResult,
        RuntimeExecutionOutcome,
        RuntimeTurnPlan,
    )
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
    from apeiria.conversation.models import ChatSessionIdentity


class RuntimeReplyPersistence(Protocol):
    """Required persistence collaborator for the runtime commit stage."""

    async def persist_tool_observations(
        self,
        *,
        turn: "RuntimeTurnInput",
        generation: "RuntimeExecutionOutcome",
        trace_id: str,
    ) -> str: ...

    async def persist_assistant_message(  # noqa: PLR0913
        self,
        *,
        turn: "RuntimeTurnInput",
        context: "RuntimeContextMaterials",
        social_decision: "ReplyStrategyDecision",
        plan: "RuntimeTurnPlan",
        generation: "RuntimeExecutionOutcome",
        trace_id: str,
    ) -> None: ...

    async def rebuild_context_window(
        self,
        *,
        identity: "ChatSessionIdentity",
    ) -> None: ...


class RuntimeReplyAccounting(Protocol):
    """Reply-strategy accounting collaborator for generated turns."""

    def notify_replied(self, session_id: str) -> None: ...


class RuntimeDeliverySender(Protocol):
    """Optional delivery collaborator for proactive generated replies."""

    def __call__(
        self,
        turn: "RuntimeTurnInput",
        reply_text: str,
        *,
        trace_id: str = "",
    ) -> "RuntimeDeliveryOutcome | None | Awaitable[RuntimeDeliveryOutcome | None]": ...


class RuntimeDeliveryOutcome(Protocol):
    """Delivery result shape consumed by runtime commit."""

    @property
    def delivered(self) -> bool: ...


class RuntimeDeliveryOutcomeFull(RuntimeDeliveryOutcome, Protocol):
    """Full delivery result shape stored on runtime stage records."""

    @property
    def error(self) -> str | None: ...

    @property
    def reason(self) -> str | None: ...

    @property
    def channel(self) -> str | None: ...

    @property
    def remote_message_id(self) -> str | None: ...


class RuntimeContextUsageRecorder(Protocol):
    """Optional prompt-window usage accounting collaborator."""

    def __call__(
        self,
        session_id: str,
        *,
        response: "AIModelGenerateResponse",
        message_count: int,
    ) -> None: ...


class RuntimeAmbientReplyRecorder(Protocol):
    """Subset of session runtime accounting used by commit."""

    def record_ambient_reply(self, *, now: "datetime") -> None: ...


@dataclass(frozen=True, slots=True)
class RuntimeCommitEffectsStage:
    """Commit post-execution side effects with structured substep status."""

    reply_persistence: RuntimeReplyPersistence
    reply_strategy_service: RuntimeReplyAccounting
    deliver_reply: RuntimeDeliverySender | None = None
    record_context_usage: RuntimeContextUsageRecorder | None = None

    async def commit(
        self,
        *,
        commit_input: "RuntimeCommitInput",
    ) -> "RuntimeCommitResult":
        from apeiria.app.ai.runtime.stages import RuntimeCommitResult

        turn = commit_input.turn
        context = commit_input.context
        generation = commit_input.generation
        response = generation.response
        reply_text = response.content.strip() if response is not None else ""
        substeps: dict[str, str] = {}
        commit_status = "committed"

        delivery_result = await self._deliver_generated_reply(
            turn=turn,
            reply_text=reply_text,
            trace_id=commit_input.trace_id,
        )
        if delivery_result is None:
            substeps["delivery"] = "not_required"
        elif delivery_result.delivered:
            substeps["delivery"] = "committed"
        else:
            substeps["delivery"] = "failed"
            commit_status = "partial"

        generation_with_delivery = cast(
            "RuntimeExecutionOutcome",
            replace(generation, delivery_result=delivery_result),
        )
        required_failed = await self._persist_required_outputs(
            turn=turn,
            context=context,
            social_decision=commit_input.social_decision,
            plan=commit_input.plan,
            generation=generation_with_delivery,
            trace_id=commit_input.trace_id,
            substeps=substeps,
        )
        if required_failed:
            return RuntimeCommitResult(
                stage="commit",
                reply_text="",
                delivery_result=delivery_result,
                commit_status="failed",
                substeps=substeps,
            )

        await self._rebuild_context_window(
            turn=turn,
            substeps=substeps,
        )
        self._record_reply_accounting(
            turn=turn,
            response=response,
            context=context,
            generation=generation_with_delivery,
            hard_decision=commit_input.hard_decision,
            current_time=commit_input.current_time,
            session_runtime=commit_input.session_runtime,
            substeps=substeps,
        )
        if any(status == "failed" for status in substeps.values()):
            commit_status = "partial"
        return RuntimeCommitResult(
            stage="commit",
            reply_text=reply_text,
            delivery_result=delivery_result,
            commit_status=commit_status,
            substeps=substeps,
        )

    async def _deliver_generated_reply(
        self,
        *,
        turn: "RuntimeTurnInput",
        reply_text: str,
        trace_id: str,
    ) -> "RuntimeDeliveryOutcome | None":
        if self.deliver_reply is None:
            return None
        result = self.deliver_reply(
            turn,
            reply_text,
            trace_id=trace_id,
        )
        if inspect.isawaitable(result):
            return await result
        return result

    async def _persist_required_outputs(  # noqa: PLR0913
        self,
        *,
        turn: "RuntimeTurnInput",
        context: "RuntimeContextMaterials",
        social_decision: "ReplyStrategyDecision",
        plan: "RuntimeTurnPlan",
        generation: "RuntimeExecutionOutcome",
        trace_id: str,
        substeps: dict[str, str],
    ) -> bool:
        try:
            status = await self.reply_persistence.persist_tool_observations(
                turn=turn,
                generation=generation,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace {} failed tool-observation persistence for session {}",
                trace_id,
                turn.identity.session_id,
            )
            substeps["tool_observations"] = "failed"
            return True
        substeps["tool_observations"] = status

        try:
            await self.reply_persistence.persist_assistant_message(
                turn=turn,
                context=context,
                social_decision=social_decision,
                plan=plan,
                generation=generation,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace {} failed assistant persistence for session {}",
                trace_id,
                turn.identity.session_id,
            )
            substeps["assistant_message"] = "failed"
            return True
        substeps["assistant_message"] = "committed"
        return False

    async def _rebuild_context_window(
        self,
        *,
        turn: "RuntimeTurnInput",
        substeps: dict[str, str],
    ) -> None:
        try:
            await self.reply_persistence.rebuild_context_window(
                identity=turn.identity,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI context-window rebuild failed for session {}",
                turn.identity.session_id,
            )
            substeps["context_window"] = "failed"
            return
        substeps["context_window"] = "committed"

    def _record_reply_accounting(  # noqa: PLR0913
        self,
        *,
        turn: "RuntimeTurnInput",
        response: "AIModelGenerateResponse | None",
        context: "RuntimeContextMaterials",
        generation: "RuntimeExecutionOutcome",
        hard_decision: "RuntimeHardRuleDecision",
        current_time: "datetime",
        session_runtime: RuntimeAmbientReplyRecorder | None,
        substeps: dict[str, str],
    ) -> None:
        try:
            if self.record_context_usage is not None and response is not None:
                self.record_context_usage(
                    turn.identity.session_id,
                    response=response,
                    message_count=len(context.turns),
                )
            if (
                generation.delivery_result is None
                or generation.delivery_result.delivered
            ):
                self.reply_strategy_service.notify_replied(turn.identity.session_id)
                if session_runtime is not None and hard_decision.reason_codes == (
                    "ambient_candidate",
                ):
                    session_runtime.record_ambient_reply(now=current_time)
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace accounting failed for session {}",
                turn.identity.session_id,
            )
            substeps["reply_accounting"] = "failed"
            return
        substeps["reply_accounting"] = "committed"


__all__ = [
    "RuntimeAmbientReplyRecorder",
    "RuntimeCommitEffectsStage",
    "RuntimeContextUsageRecorder",
    "RuntimeDeliverySender",
    "RuntimeReplyAccounting",
    "RuntimeReplyPersistence",
]
