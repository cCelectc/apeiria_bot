"""Text presenters for owner admin commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.i18n import t

if TYPE_CHECKING:
    from collections.abc import Iterable

MAX_TEXT_LENGTH = 120
LIST_PREVIEW_LIMIT = 5
DICT_PREVIEW_LIMIT = 4


def render_block(
    title: str,
    fields: Iterable[tuple[str, object]],
    *,
    summary: str | None = None,
    footer: str | None = None,
) -> str:
    """Render one titled key-value text block."""
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
    """Render one titled text block with bullet list items."""
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


def summarize_value(key: str, value: object) -> str:
    """Render one configuration value for chat output."""
    key_lower = key.lower()
    if any(token in key_lower for token in ("token", "secret", "password", "key")):
        return t("admin.config.masked")
    return _stringify(value)


def _stringify(value: object) -> str:
    if value is None:
        result = t("admin.common.none")
    elif isinstance(value, bool):
        result = t("admin.common.enabled") if value else t("admin.common.disabled")
    elif isinstance(value, (int, float)):
        result = str(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            result = t("admin.common.empty")
        else:
            result = (
                stripped
                if len(stripped) <= MAX_TEXT_LENGTH
                else f"{stripped[: MAX_TEXT_LENGTH - 3]}..."
            )
    elif isinstance(value, list):
        result = _stringify_list(value)
    elif isinstance(value, dict):
        result = _stringify_dict(value)
    else:
        result = str(value)
    return result


def _stringify_list(value: list[object]) -> str:
    if not value:
        return t("admin.common.empty")
    preview = ", ".join(_stringify(item) for item in value[:LIST_PREVIEW_LIMIT])
    return preview if len(value) <= LIST_PREVIEW_LIMIT else f"{preview} ..."


def _stringify_dict(value: dict[object, object]) -> str:
    if not value:
        return t("admin.common.empty")
    preview = ", ".join(
        f"{key}={_stringify(item)}"
        for key, item in list(value.items())[:DICT_PREVIEW_LIMIT]
    )
    return preview if len(value) <= DICT_PREVIEW_LIMIT else f"{preview} ..."
