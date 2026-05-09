"""Provider-neutral model response normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)


@dataclass(frozen=True)
class VisibleReasoningSanitization:
    """Result of stripping user-visible inline reasoning."""

    text: str
    reasoning_stripped: bool = False
    metadata: dict[str, object] | None = None


def sanitize_visible_reasoning(text: str) -> VisibleReasoningSanitization:
    """Strip inline think-tag reasoning from user-visible text."""

    complete_blocks = len(_THINK_BLOCK_RE.findall(text))
    sanitized = _THINK_BLOCK_RE.sub("", text)
    stripped_blocks = complete_blocks
    open_match = _THINK_OPEN_RE.search(sanitized)
    if open_match is not None:
        sanitized = sanitized[: open_match.start()]
        stripped_blocks += 1
    if stripped_blocks == 0:
        return VisibleReasoningSanitization(text=text)
    return VisibleReasoningSanitization(
        text=sanitized.strip(),
        reasoning_stripped=True,
        metadata={
            "visible_reasoning_stripped": True,
            "stripped_reasoning_blocks": stripped_blocks,
        },
    )


__all__ = ["VisibleReasoningSanitization", "sanitize_visible_reasoning"]
