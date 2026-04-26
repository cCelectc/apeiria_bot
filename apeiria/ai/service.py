"""AI domain status helpers used by the builtin AI plugin shell."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIServiceStatus:
    """Status payload for the currently loaded AI runtime."""

    phase: str
    summary: str


class AIService:
    """Facade for reporting the current AI runtime status."""

    def get_status(self) -> AIServiceStatus:
        return AIServiceStatus(
            phase="runtime_active",
            summary=(
                "AI plugin is active across runtime messaging, memory, tools, "
                "admin, and session-read surfaces."
            ),
        )


ai_service = AIService()
