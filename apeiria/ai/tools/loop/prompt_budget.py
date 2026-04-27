"""Prompt-budget helpers for model-visible tool-loop messages."""

from __future__ import annotations

from apeiria.ai.model.runtime.adapter import AIModelMessage
from apeiria.ai.turn_records import PromptSafeObservation

DEFAULT_OBSERVATION_CHAR_LIMIT = 1200
RECOVERY_OBSERVATION_CHAR_LIMIT = 320
RECOVERY_OLDER_MESSAGE_CHAR_LIMIT = 800
RECOVERY_RECENT_MESSAGE_COUNT = 4
_CONTEXT_PRESSURE_MARKERS = (
    "prompt_too_long",
    "context_length_exceeded",
    "maximum context",
    "too many tokens",
    "context window",
    "413",
)


def build_prompt_safe_observation(
    content: str,
    *,
    char_limit: int = DEFAULT_OBSERVATION_CHAR_LIMIT,
) -> PromptSafeObservation:
    """Return the model-visible preview for one tool observation."""

    normalized = str(content or "")
    original_length = len(normalized)
    if char_limit <= 0 or original_length <= char_limit:
        return PromptSafeObservation(
            content=normalized,
            truncated=False,
            original_length=original_length,
        )

    marker = "\n[truncated]"
    keep = max(char_limit - len(marker), 0)
    return PromptSafeObservation(
        content=f"{normalized[:keep].rstrip()}{marker}",
        truncated=True,
        original_length=original_length,
    )


def recover_prompt_budget_messages(
    messages: tuple[AIModelMessage, ...],
) -> tuple[tuple[AIModelMessage, ...], int]:
    """Shrink model-visible history for one context-pressure retry."""

    compacted = 0
    recovered: list[AIModelMessage] = []
    recent_start = max(len(messages) - RECOVERY_RECENT_MESSAGE_COUNT, 0)
    for index, message in enumerate(messages):
        should_compact = message.role == "tool" or (
            index < recent_start
            and len(message.content) > RECOVERY_OLDER_MESSAGE_CHAR_LIMIT
        )
        if should_compact and len(message.content) > RECOVERY_OBSERVATION_CHAR_LIMIT:
            safe = build_prompt_safe_observation(
                message.content,
                char_limit=RECOVERY_OBSERVATION_CHAR_LIMIT,
            )
            recovered.append(
                AIModelMessage(
                    role=message.role,
                    content=safe.content,
                    tool_call_id=message.tool_call_id,
                    tool_calls=message.tool_calls,
                )
            )
            compacted += 1
            continue
        recovered.append(message)
    return tuple(recovered), compacted


def is_context_pressure_error(message: str) -> bool:
    normalized = message.lower()
    return any(marker in normalized for marker in _CONTEXT_PRESSURE_MARKERS)
