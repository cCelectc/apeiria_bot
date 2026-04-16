"""Layer 2: Initiative budget — per-session state + rules, no LLM.

Controls whether a group ``candidate`` message is worth spending an LLM
call on.  Direct-engagement messages (``@mention``, private) skip this
layer entirely.
"""

from __future__ import annotations

import time

from apeiria.app.ai.reply_strategy.models import (
    InitiativeBudgetResult,
    InitiativeState,
)

# -- Tunable constants (initial values) --
COOLDOWN_SECONDS: float = 30.0
MAX_REPLIES_IN_WINDOW: int = 3
WINDOW_SECONDS: float = 300.0
SILENCE_THRESHOLD: int = 15
BASE_WEIGHT: float = 0.5
BUDGET_THRESHOLD: float = 0.35


def check_initiative_budget(
    state: InitiativeState,
    *,
    initiative_bias: float,
    current_time: float | None = None,
) -> InitiativeBudgetResult:
    """Evaluate whether the bot's initiative budget allows LLM evaluation.

    Parameters
    ----------
    state:
        Mutable per-session state — the caller is expected to have already
        incremented ``consecutive_silence`` for this message.
    initiative_bias:
        Relationship-driven bias from ``EmotionProjection.initiative_bias``
        (typically -0.3 … +0.5).
    current_time:
        Epoch seconds.  Defaults to ``time.time()``.
    """

    now = current_time if current_time is not None else time.time()

    # 1. Cooldown: too soon after last reply
    if state.last_reply_at is not None:
        elapsed = now - state.last_reply_at
        if elapsed < COOLDOWN_SECONDS:
            return InitiativeBudgetResult(
                should_evaluate=False,
                budget_score=0.0,
                reason=f"cooldown ({elapsed:.0f}s < {COOLDOWN_SECONDS:.0f}s)",
            )

    # 2. Frequency limit: too many replies in the recent window
    _prune_reply_times(state, now)
    if len(state.recent_reply_times) >= MAX_REPLIES_IN_WINDOW:
        return InitiativeBudgetResult(
            should_evaluate=False,
            budget_score=0.0,
            reason=(
                f"frequency limit ({len(state.recent_reply_times)}"
                f" >= {MAX_REPLIES_IN_WINDOW} in {WINDOW_SECONDS:.0f}s)"
            ),
        )

    # 3. Compute budget from silence accumulation + relationship bias
    silence_ratio = min(state.consecutive_silence / SILENCE_THRESHOLD, 1.0)
    budget = silence_ratio * BASE_WEIGHT + initiative_bias
    budget = max(0.0, min(1.0, budget))

    if budget < BUDGET_THRESHOLD:
        return InitiativeBudgetResult(
            should_evaluate=False,
            budget_score=budget,
            reason=(
                f"budget {budget:.2f} < threshold {BUDGET_THRESHOLD:.2f} "
                f"(silence={state.consecutive_silence}, "
                f"bias={initiative_bias:+.2f})"
            ),
        )

    return InitiativeBudgetResult(
        should_evaluate=True,
        budget_score=budget,
        reason=(
            f"budget {budget:.2f} >= threshold {BUDGET_THRESHOLD:.2f} "
            f"(silence={state.consecutive_silence}, "
            f"bias={initiative_bias:+.2f})"
        ),
    )


def record_reply(state: InitiativeState, *, current_time: float | None = None) -> None:
    """Update state after the bot replies."""

    now = current_time if current_time is not None else time.time()
    state.consecutive_silence = 0
    state.last_reply_at = now
    state.recent_reply_times.append(now)


def record_silence(state: InitiativeState) -> None:
    """Update state when a group message arrives but bot stays silent."""

    state.consecutive_silence += 1
    state.total_messages_seen += 1


def _prune_reply_times(state: InitiativeState, now: float) -> None:
    cutoff = now - WINDOW_SECONDS
    state.recent_reply_times = [t for t in state.recent_reply_times if t > cutoff]
