from __future__ import annotations

import re

from .models import ApprovalAction, ApprovalCommand

_HASHED_TICKET_RE = re.compile(r"(?<!\S)#([A-Z0-9]{4,12})(?!\S)", re.IGNORECASE)
_BARE_TICKET_RE = re.compile(r"^[A-Z0-9]{4,12}$", re.IGNORECASE)
_ACTION_ALIASES: dict[str, ApprovalAction] = {
    "同意": "approve",
    "允许": "approve",
    "通过": "approve",
    "approve": "approve",
    "pass": "approve",
    "拒绝": "reject",
    "reject": "reject",
    "忽略": "ignore",
    "ignore": "ignore",
    "详情": "detail",
    "detail": "detail",
    "列表": "list",
    "list": "list",
}
_NEEDS_TARGET: set[ApprovalAction] = {"approve", "reject", "ignore", "detail"}


def parse_approval_command(
    text: str,
    *,
    has_reply_target: bool,
    approval_prefix: str = "审批",
) -> ApprovalCommand | None:
    stripped = text.strip()
    if not stripped:
        return None

    parts = stripped.split(maxsplit=1)
    raw_action = parts[0].strip().lower()
    action = _ACTION_ALIASES.get(raw_action)
    if action is None and raw_action == approval_prefix.strip().lower():
        action = "list"
    if action is None:
        return None

    rest = parts[1].strip() if len(parts) > 1 else ""
    ticket_id, reason = _extract_ticket_id_and_reason(rest)

    missing_target = (
        action in _NEEDS_TARGET and ticket_id is None and not has_reply_target
    )
    return ApprovalCommand(
        action=action,
        ticket_id=ticket_id,
        reason=reason if action == "reject" else "",
        missing_target=missing_target,
    )


def _extract_ticket_id_and_reason(value: str) -> tuple[str | None, str]:
    stripped = value.strip()
    if not stripped:
        return None, ""

    match = _HASHED_TICKET_RE.search(stripped)
    if match is not None:
        reason = (
            stripped[: match.start()].strip() + " " + stripped[match.end() :].strip()
        ).strip()
        return match.group(1).upper(), reason

    first, _, rest = stripped.partition(" ")
    if _BARE_TICKET_RE.fullmatch(first):
        return first.upper(), rest.strip()
    return None, stripped


__all__ = ["parse_approval_command"]
