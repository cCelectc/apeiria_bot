"""Admin-side audit helper shared across AI admin mixins."""

from __future__ import annotations

from nonebot.log import logger

from apeiria.access.webui_auth.secrets import record_security_audit_event


def record_ai_admin_audit(
    event_type: str,
    *,
    actor_username: str | None = None,
    detail: str | None = None,
) -> None:
    """Record an AI admin audit event, swallowing logging failures."""

    if not actor_username:
        return
    try:
        record_security_audit_event(
            event_type,
            actor_username=actor_username,
            detail=detail,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning(
            "AI admin audit logging failed event_type={} actor={}",
            event_type,
            actor_username,
        )


__all__ = ["record_ai_admin_audit"]
