"""Prompt diagnostics for runtime planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.prompting import (
    project_reply_prompt_regions,
    prompt_region_diagnostics,
)

if TYPE_CHECKING:
    from apeiria.ai.prompting import PromptPacket


def build_prompt_region_diagnostics(packet: "PromptPacket") -> dict[str, object]:
    """Build bounded prompt-region diagnostics for one reply prompt packet."""

    return prompt_region_diagnostics(project_reply_prompt_regions(packet))


__all__ = ["build_prompt_region_diagnostics"]
