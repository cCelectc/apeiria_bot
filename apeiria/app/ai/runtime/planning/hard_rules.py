"""Deterministic hard-rule mapping for AI session runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.app.ai.reply_strategy.models import (  # noqa: TC001
    ReplyStrategyDecision,
    WakeContext,
)
from apeiria.app.ai.runtime.planning.social import (
    project_social_skip_decision,
)
from apeiria.app.ai.runtime.session.context import RuntimeTurnSource  # noqa: TC001
from apeiria.app.ai.runtime.session.runtime import (
    InMemoryAISessionRuntime,  # noqa: TC001
)
from apeiria.app.ai.runtime.strategy import (
    RuntimeHardRuleDecision,
    RuntimeHardRuleReasonCode,
)

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleAction


def decide_runtime_hard_rule(  # noqa: C901, PLR0911
    *,
    wake_context: WakeContext,
    source: RuntimeTurnSource,
    session_runtime: InMemoryAISessionRuntime | None = None,
    now: datetime | None = None,
) -> RuntimeHardRuleDecision:
    """Map existing wake/direct/source signals into a runtime hard-rule decision."""

    current_time = now or datetime.now(timezone.utc)
    event_dedupe_key = source.event_dedupe_key or source.source_message_id
    if (
        session_runtime is not None
        and not source.event_dedupe_claimed
        and not session_runtime.record_event_if_new(
            event_dedupe_key,
            now=current_time,
        )
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

    if (
        not source.message_text.strip()
        and not wake_context.message_text.strip()
        and not (
            wake_context.has_media or source.media_parts or source.media_diagnostics
        )
    ):
        return _decision(
            action="drop",
            reason_code="empty_input",
            reason_text="Message has no usable text or media content.",
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

    if session_runtime is not None and session_runtime.has_other_active_turn:
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


def social_skip_to_runtime_decision(
    decision: ReplyStrategyDecision,
) -> RuntimeHardRuleDecision:
    """Project a social no-reply decision into runtime-native hard-rule terms."""

    projection = project_social_skip_decision(decision)
    return RuntimeHardRuleDecision(
        action=projection.action,
        reason_codes=(projection.reason_code,),
        reason_text=projection.reason_text,
        evidence=projection.evidence,
        should_observe=projection.should_observe,
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
    if source.event_dedupe_key:
        evidence["event_dedupe_key"] = source.event_dedupe_key
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
