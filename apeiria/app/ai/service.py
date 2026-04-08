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
            phase="phase_11_minimal_reply_loop",
            summary=(
                "AI plugin shell is loaded with context ingestion, persona/model "
                "binding, provider dispatch, and minimal auto-reply flow."
            ),
        )


ai_service = AIService()
