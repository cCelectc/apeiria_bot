"""Shared auth helpers for AI web UI routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


def actor_username_from_claims(session: "AuthSession") -> str | None:
    """Extract an actioning username from a session's identity claims."""

    username = getattr(session, "username", "")
    if not isinstance(username, str):
        return None
    username = username.strip()
    return username or None
