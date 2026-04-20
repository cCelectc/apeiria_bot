"""Minimal AI domain service used by the builtin AI plugin shell."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIServiceStatus:
    """Static status payload for the early AI plugin skeleton."""

    phase: str
    summary: str


class AIService:
    """Small facade for reporting the active AI rewrite milestone."""

    def get_status(self) -> AIServiceStatus:
        return AIServiceStatus(
            phase="phase_16_cleanup_in_progress",
            summary=(
                "AI plugin shell now runs through runtime, model, skill, and "
                "admin boundaries while legacy orchestration and admin files "
                "remain as compatibility shims."
            ),
        )


ai_service = AIService()
