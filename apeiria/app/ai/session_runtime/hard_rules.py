"""Deterministic hard-rule mapping for AI session runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.app.ai.reply_strategy.models import (  # noqa: TC001
    ReplyStrategyDecision,
    WakeContext,
)

from .context import RuntimeTurnSource  # noqa: TC001
from .runtime import InMemoryAISessionRuntime  # noqa: TC001
from .strategy import RuntimeHardRuleDecision, RuntimeHardRuleReasonCode

if TYPE_CHECKING:
    from .strategy import RuntimeHardRuleAction


def decide_runtime_hard_rule(  # noqa: C901, PLR0911
    *,
    wake_context: WakeContext,
    source: RuntimeTurnSource,
    session_runtime: InMemoryAISessionRuntime | None = None,
    now: datetime | None = None,
) -> RuntimeHardRuleDecision:
    """Map existing wake/direct/source signals into a runtime hard-rule decision."""

    current_time = now or datetime.now(timezone.utc)
    if session_runtime is not None and not session_runtime.record_event_if_new(
        source.source_message_id,
        now=current_time,
    ):
        return _decision(
            action="drop",
            reason_code="duplicate_event",
            reason_text="Duplicate event was ignored.",
            wake_context=wake_context,
            source=source,
            should_observe=False,
            should_reply=False,
        )

    if wake_context.user_id == wake_context.bot_self_id:
        return _decision(
            action="drop",
            reason_code="bot_self_message",
            reason_text="Message was sent by the bot itself.",
            wake_context=wake_context,
            source=source,
            should_observe=False,
            should_reply=False,
        )

    if not source.message_text.strip() or not wake_context.message_text.strip():
        return _decision(
            action="drop",
            reason_code="empty_input",
            reason_text="Message has no usable text content.",
            wake_context=wake_context,
            source=source,
            should_observe=False,
            should_reply=False,
        )

    is_priority_input = (
        wake_context.is_future_task
        or source.runtime_mode == "future_task"
        or wake_context.is_tome
        or source.direct_signal
        or wake_context.is_private
        or source.is_private
    )
    if (
        session_runtime is not None
        and not is_priority_input
        and wake_context.allow_group_initiative
        and session_runtime.should_merge_ambient(now=current_time)
    ):
        merge = session_runtime.record_pending_ambient(source, now=current_time)
        return _decision(
            action="merge",
            reason_code="ambient_merge_window",
            reason_text="Ambient input was merged into pending session context.",
            wake_context=wake_context,
            source=source,
            should_observe=True,
            should_reply=False,
            extra_evidence={
                "merged_message_ids": merge.merged_message_ids,
                "merged_message_count": merge.merged_message_count,
            },
        )

    if session_runtime is not None and session_runtime.is_active:
        session_runtime.record_defer(
            reason="session_busy",
            queued_at=current_time,
            now=current_time,
        )
        return _decision(
            action="defer",
            reason_code="session_busy",
            reason_text="Session already has an active turn.",
            wake_context=wake_context,
            source=source,
            should_observe=True,
            should_reply=False,
            extra_evidence={"session_active": True},
        )

    if wake_context.is_future_task or source.runtime_mode == "future_task":
        return _decision(
            action="continue",
            reason_code="future_task",
            reason_text="Future task bypasses ambient initiative budget.",
            wake_context=wake_context,
            source=source,
            should_observe=True,
            should_reply=True,
        )

    if wake_context.is_tome or source.direct_signal:
        return _decision(
            action="continue",
            reason_code="direct_signal",
            reason_text="Input directly addresses the bot.",
            wake_context=wake_context,
            source=source,
            should_observe=True,
            should_reply=True,
        )

    if wake_context.is_private or source.is_private:
        return _decision(
            action="continue",
            reason_code="private_message",
            reason_text="Private message bypasses ambient initiative budget.",
            wake_context=wake_context,
            source=source,
            should_observe=True,
            should_reply=True,
        )

    if not wake_context.allow_group_initiative:
        return _decision(
            action="observe",
            reason_code="initiative_disabled",
            reason_text="Ambient group initiative is disabled.",
            wake_context=wake_context,
            source=source,
            should_observe=True,
            should_reply=False,
        )

    if session_runtime is not None:
        block_evidence = session_runtime.ambient_reply_block_evidence(now=current_time)
        if block_evidence:
            return _decision(
                action="observe",
                reason_code="ambient_cooldown",
                reason_text="Ambient reply budget is cooling down.",
                wake_context=wake_context,
                source=source,
                should_observe=True,
                should_reply=False,
                extra_evidence=block_evidence,
            )

    return _decision(
        action="continue",
        reason_code="ambient_candidate",
        reason_text="Ambient group input is eligible for later judgment.",
        wake_context=wake_context,
        source=source,
        should_observe=True,
        should_reply=True,
    )


def map_legacy_skip_to_runtime_decision(
    decision: ReplyStrategyDecision,
) -> RuntimeHardRuleDecision:
    """Project a legacy no-reply strategy result into runtime vocabulary."""

    reason_text = decision.reason_text or ",".join(decision.reason_codes)
    reason_blob = " ".join((*decision.reason_codes, reason_text)).lower()
    if decision.action == "drop":
        action: RuntimeHardRuleAction = "drop"
        reason_code: RuntimeHardRuleReasonCode = "policy_denied"
        should_observe = False
    elif "wait" in reason_blob:
        action = "wait"
        reason_code = "ambient_merge_window"
        should_observe = True
    elif "busy" in reason_blob or "rate" in reason_blob:
        action = "defer"
        reason_code = "session_busy"
        should_observe = True
    else:
        action = "observe"
        reason_code = "ambient_weak_relevance"
        should_observe = True

    return RuntimeHardRuleDecision(
        action=action,
        reason_codes=(reason_code,),
        reason_text=reason_text,
        evidence={
            "legacy_action": decision.action,
            "legacy_decision_source": decision.decision_source,
            "legacy_reason_codes": decision.reason_codes,
        },
        should_observe=should_observe,
        should_reply=False,
    )


def _decision(  # noqa: PLR0913
    *,
    action: "RuntimeHardRuleAction",
    reason_code: RuntimeHardRuleReasonCode,
    reason_text: str,
    wake_context: WakeContext,
    source: RuntimeTurnSource,
    should_observe: bool,
    should_reply: bool,
    extra_evidence: dict[str, object] | None = None,
) -> RuntimeHardRuleDecision:
    evidence = {
        "user_id": wake_context.user_id,
        "source_message_id": source.source_message_id,
        "runtime_mode": source.runtime_mode,
        "direct_signal": wake_context.is_tome or source.direct_signal,
        "is_private": wake_context.is_private or source.is_private,
        "allow_group_initiative": wake_context.allow_group_initiative,
    }
    if extra_evidence:
        evidence.update(extra_evidence)
    return RuntimeHardRuleDecision(
        action=action,
        reason_codes=(reason_code,),
        reason_text=reason_text,
        evidence=evidence,
        should_observe=should_observe,
        should_reply=should_reply,
    )
