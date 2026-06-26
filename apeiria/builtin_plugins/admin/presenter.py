from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

MAX_TEXT_LENGTH = 120
LIST_PREVIEW_LIMIT = 5


def render_block(
    title: str,
    fields: Iterable[tuple[str, object]],
    *,
    summary: str | None = None,
    footer: str | None = None,
) -> str:
    lines = [f"【{title}】"]
    if summary:
        lines.extend(["", summary])

    normalized_fields = [
        (label, _stringify(value)) for label, value in fields if _stringify(value)
    ]
    if normalized_fields:
        lines.append("")
        lines.extend(f"- {label}: {value}" for label, value in normalized_fields)

    if footer:
        lines.extend(["", footer])

    return "\n".join(lines)


def render_list_block(
    title: str,
    items: Iterable[str],
    *,
    summary: str | None = None,
    empty_message: str | None = None,
    footer: str | None = None,
) -> str:
    lines = [f"【{title}】"]
    if summary:
        lines.extend(["", summary])

    normalized_items = [item.strip() for item in items if item and item.strip()]
    lines.append("")
    if normalized_items:
        lines.extend(normalized_items)
    elif empty_message:
        lines.append(empty_message)

    if footer:
        lines.extend(["", footer])
    return "\n".join(lines)


def _stringify(value: object) -> str:  # noqa: PLR0911
    if value is None:
        return "无"
    if isinstance(value, bool):
        return "启用" if value else "禁用"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "(空)"
        if len(stripped) > MAX_TEXT_LENGTH:
            return f"{stripped[: MAX_TEXT_LENGTH - 3]}..."
        return stripped
    if isinstance(value, list):
        preview = ", ".join(_stringify(v) for v in value[:LIST_PREVIEW_LIMIT])
        if len(value) > LIST_PREVIEW_LIMIT:
            return f"{preview} ..."
        return preview or "(空)"
    return str(value)
