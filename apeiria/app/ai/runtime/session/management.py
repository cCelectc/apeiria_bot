"""Runtime helpers for applying managed AI session state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision

if TYPE_CHECKING:
    from apeiria.app.ai.sessions.models import AISessionManagementRecord


def managed_session_disabled_decision(
    managed_session: AISessionManagementRecord,
) -> RuntimeHardRuleDecision | None:
    """Return a skip decision when session management disables AI replies."""

    if managed_session.ai_enabled:
        return None
    return RuntimeHardRuleDecision(
        action="observe",
        reason_codes=("session_ai_disabled",),
        reason_text="AI replies are disabled for this session.",
        evidence={
            "session_id": managed_session.session_id,
            "platform_id": managed_session.source_identity.identity.platform_id,
            "message_type": managed_session.source_identity.identity.message_type,
        },
        should_observe=True,
        should_reply=False,
    )


def managed_session_diagnostics(
    managed_session: AISessionManagementRecord | None,
) -> tuple[str, ...]:
    """Project managed session state into prompt-safe diagnostic labels."""

    if managed_session is None:
        return ("session_management:unmanaged",)
    diagnostics = [
        f"session_ai_enabled:{str(managed_session.ai_enabled).lower()}",
    ]
    if managed_session.persona_id:
        diagnostics.append(f"session_persona:{managed_session.persona_id}")
    if managed_session.context_reset_at is not None:
        diagnostics.append(
            f"session_context_reset_at:{managed_session.context_reset_at.isoformat()}"
        )
    if not managed_session.ai_enabled:
        diagnostics.append("session_ai_disabled")
    return tuple(diagnostics)


__all__ = ["managed_session_diagnostics", "managed_session_disabled_decision"]
