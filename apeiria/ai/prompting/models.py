"""Provider-neutral prompt packet primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PromptPurpose = Literal[
    "reply_planner",
    "reply_final",
    "social_judgment",
    "memory_extraction",
    "conversation_summary",
    "skill_selection",
    "tool_intent_planning",
]
PromptSectionRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class PromptSection:
    """One named prompt block with a model-visible role."""

    role: PromptSectionRole
    name: str
    content: str


@dataclass(frozen=True)
class PromptPacket:
    """One ordered model-call prompt assembled for a concrete purpose."""

    purpose: PromptPurpose
    sections: tuple[PromptSection, ...]
