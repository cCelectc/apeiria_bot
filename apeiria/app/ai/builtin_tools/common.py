"""Shared runtime helpers for app-owned internal AI tool executors."""

from __future__ import annotations

from datetime import datetime

from apeiria.ai.tools.models import AIToolExecutionContext, AIToolResult

MAX_CONTENT_CHARS = 500


def context_payload(context: AIToolExecutionContext) -> dict[str, object | None]:
    return {
        "session_id": context.session_id,
        "source_message_id": context.source_message_id,
        "actor_id": context.actor_id,
        "chat_scope_type": context.chat_scope_type,
        "chat_scope_id": context.chat_scope_id,
        "reply_audience": context.reply_audience,
    }


def parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def clean_required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"{field} is required"
        raise ValueError(msg)
    return value.strip()


def bounded_text(text: str, *, max_chars: int = MAX_CONTENT_CHARS) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3].rstrip()}..."


def short_text(text: str) -> str:
    return bounded_text(text, max_chars=120)


def bounded_int(
    value: int | None,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def bounded_float(value: float | None, *, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(parsed, 1.0))


def optional_choice(
    value: str | None,
    choices: set[str],
    *,
    default: str | None = None,
) -> str | None:
    if value is None:
        return default
    normalized = value.strip()
    if normalized in choices:
        return normalized
    return default


def error_result(tool_name: str, message: str) -> AIToolResult:
    return AIToolResult(
        summary=f"- [{tool_name}] failed: {message}",
        output_payload={"ok": False, "error": message},
        status="error",
    )


def denied_result(tool_name: str, message: str) -> AIToolResult:
    return AIToolResult(
        summary=f"- [{tool_name}] denied: {message}",
        output_payload={"ok": False, "error": message},
        status="denied",
    )
