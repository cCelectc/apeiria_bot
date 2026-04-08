"""Minimal AI domain service used by the builtin AI plugin skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIServiceStatus:
    """Static status payload for the early AI plugin skeleton."""

    phase: str
    summary: str


class AIService:
    """Small facade for the phase-1 AI plugin skeleton.

    The real AI domain logic will land in later phases under dedicated
    subpackages. This service only exposes enough state for a safe plugin
    smoke test and a minimal operator command.
    """

    def get_status(self) -> AIServiceStatus:
        return AIServiceStatus(
            phase="phase_1_skeleton",
            summary=(
                "AI plugin skeleton is loaded. Context, persona, and memory "
                "domains are not implemented yet."
            ),
        )


ai_service = AIService()
