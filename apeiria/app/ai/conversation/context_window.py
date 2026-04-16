"""Dynamic context window sizing with time decay and reply-chain rescue.

Uses feedback from model API ``usage.prompt_tokens`` to self-calibrate
the number of messages that fit in the context budget, without any
external tokenizer dependency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import ChatContextMessageView

# -- Tunable constants --
DEFAULT_CONTEXT_TOKEN_LIMIT: int = 4096
DEFAULT_TOKENS_PER_MESSAGE: float = 100.0
DEFAULT_OVERHEAD_TOKENS: int = 800
MIN_KEEP_MESSAGES: int = 2
MAX_FETCH_MESSAGES: int = 50
EMA_ALPHA: float = 0.3

RECENCY_WINDOW_SECONDS: float = 30.0 * 60  # 30 minutes
STALENESS_HALF_LIFE_SECONDS: float = 120.0 * 60  # 2 hours
STALENESS_CUTOFF_SECONDS: float = 240.0 * 60  # 4 hours

REPLY_CONTEXT_RADIUS: int = 1

_MAX_CALIBRATIONS: int = 500
_CALIBRATION_TTL_SECONDS: float = 3600.0


@dataclass
class ContextCalibration:
    """Per-session token calibration state (in-memory only)."""

    tokens_per_message: float = DEFAULT_TOKENS_PER_MESSAGE
    overhead_tokens: float = DEFAULT_OVERHEAD_TOKENS
    sample_count: int = 0
    last_active_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ContextWindowResult:
    """Result of splitting messages into kept + overflow."""

    kept_messages: list["ChatContextMessageView"]
    overflow_messages: list["ChatContextMessageView"]
    target_max_messages: int
    needs_compression: bool


class ContextWindowService:
    """Manages dynamic context window sizing via feedback from model usage."""

    def __init__(self) -> None:
        self._calibrations: dict[str, ContextCalibration] = {}

    def compute_window(
        self,
        messages: list["ChatContextMessageView"],
        *,
        session_id: str,
        context_token_limit: int = DEFAULT_CONTEXT_TOKEN_LIMIT,
        current_time: float | None = None,
    ) -> ContextWindowResult:
        """Split messages into kept + overflow based on calibrated budget."""

        if not messages:
            return ContextWindowResult(
                kept_messages=[],
                overflow_messages=[],
                target_max_messages=0,
                needs_compression=False,
            )

        cal = self._get_calibration(session_id)
        now = current_time if current_time is not None else time.time()

        # Estimate how many messages fit in the conversation portion of budget
        conversation_budget = max(context_token_limit - cal.overhead_tokens, 200.0)
        target_max = max(
            MIN_KEEP_MESSAGES,
            int(conversation_budget / max(cal.tokens_per_message, 1.0)),
        )

        # Score each message by time-based weight
        scored = _score_messages_by_time(messages, now=now)

        # Select top target_max by score (preserving time order in output)
        kept_indices = _select_top_indices(scored, max_keep=target_max)

        # Rescue reply-chain referenced messages from overflow
        kept_indices = _rescue_reply_chains(messages, kept_indices)

        kept = [messages[i] for i in sorted(kept_indices)]
        overflow = [messages[i] for i in range(len(messages)) if i not in kept_indices]

        return ContextWindowResult(
            kept_messages=kept,
            overflow_messages=overflow,
            target_max_messages=target_max,
            needs_compression=bool(overflow),
        )

    def record_usage(
        self,
        session_id: str,
        *,
        prompt_tokens: int,
        message_count: int,
    ) -> None:
        """Update calibration from actual API usage data."""

        if message_count <= 0 or prompt_tokens <= 0:
            return

        cal = self._get_calibration(session_id)

        # Estimate per-message tokens (subtract overhead estimate)
        estimated_conversation_tokens = max(
            prompt_tokens - cal.overhead_tokens, message_count
        )
        actual_per_msg = estimated_conversation_tokens / message_count

        if cal.sample_count == 0:
            cal.tokens_per_message = actual_per_msg
            cal.overhead_tokens = max(
                prompt_tokens - actual_per_msg * message_count, 0.0
            )
        else:
            alpha = EMA_ALPHA
            cal.tokens_per_message = (
                cal.tokens_per_message * (1 - alpha) + actual_per_msg * alpha
            )
            new_overhead = prompt_tokens - cal.tokens_per_message * message_count
            cal.overhead_tokens = (
                cal.overhead_tokens * (1 - alpha) + max(new_overhead, 0.0) * alpha
            )

        cal.sample_count += 1
        cal.last_active_at = time.time()

    def _get_calibration(self, session_id: str) -> ContextCalibration:
        cal = self._calibrations.get(session_id)
        if cal is None:
            self._maybe_evict()
            cal = ContextCalibration()
            self._calibrations[session_id] = cal
        cal.last_active_at = time.time()
        return cal

    def _maybe_evict(self) -> None:
        if len(self._calibrations) < _MAX_CALIBRATIONS:
            return
        now = time.time()
        stale = [
            sid
            for sid, cal in self._calibrations.items()
            if now - cal.last_active_at > _CALIBRATION_TTL_SECONDS
        ]
        for sid in stale:
            del self._calibrations[sid]
        if len(self._calibrations) >= _MAX_CALIBRATIONS:
            oldest = sorted(
                self._calibrations,
                key=lambda s: self._calibrations[s].last_active_at,
            )
            for sid in oldest[: len(oldest) // 4]:
                del self._calibrations[sid]


def _score_messages_by_time(
    messages: list["ChatContextMessageView"],
    *,
    now: float,
) -> list[tuple[int, float]]:
    """Return (index, time_weight) pairs for all messages."""

    scored: list[tuple[int, float]] = []
    for i, msg in enumerate(messages):
        msg_epoch = msg.created_at.timestamp()
        age_seconds = max(now - msg_epoch, 0.0)

        if age_seconds <= RECENCY_WINDOW_SECONDS:
            weight = 1.0
        elif age_seconds >= STALENESS_CUTOFF_SECONDS:
            weight = 0.0
        else:
            decay_progress = (
                age_seconds - RECENCY_WINDOW_SECONDS
            ) / STALENESS_HALF_LIFE_SECONDS
            weight = max(0.1, 1.0 - decay_progress * 0.5)

        scored.append((i, weight))
    return scored


def _select_top_indices(
    scored: list[tuple[int, float]],
    *,
    max_keep: int,
) -> set[int]:
    """Select the top-scored message indices, ensuring MIN_KEEP most recent."""

    if not scored:
        return set()

    # Always keep the most recent MIN_KEEP messages regardless of score
    all_indices = [idx for idx, _ in scored]
    recent_must_keep = set(all_indices[-MIN_KEEP_MESSAGES:])

    # Sort remaining by (weight desc, index desc) — prefer recent among ties
    candidates = sorted(
        scored,
        key=lambda pair: (pair[1], pair[0]),
        reverse=True,
    )
    selected = set(recent_must_keep)
    for idx, _ in candidates:
        if len(selected) >= max_keep:
            break
        selected.add(idx)

    return selected


def _rescue_reply_chains(
    messages: list["ChatContextMessageView"],
    kept_indices: set[int],
) -> set[int]:
    """Pull reply-referenced messages (and neighbors) from overflow into kept."""

    msg_id_to_index: dict[str, int] = {
        msg.message_id: i for i, msg in enumerate(messages)
    }

    rescued: set[int] = set()
    for idx in kept_indices:
        reply_id = messages[idx].reply_to_message_id
        if not reply_id:
            continue
        target_idx = msg_id_to_index.get(reply_id)
        if target_idx is None or target_idx in kept_indices:
            continue
        # Rescue the referenced message and its neighbors
        lo = max(target_idx - REPLY_CONTEXT_RADIUS, 0)
        hi = min(target_idx + REPLY_CONTEXT_RADIUS + 1, len(messages))
        for i in range(lo, hi):
            if i not in kept_indices:
                rescued.add(i)

    return kept_indices | rescued


context_window_service = ContextWindowService()
