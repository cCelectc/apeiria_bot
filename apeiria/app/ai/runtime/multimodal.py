"""Runtime multimodal source projection helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from apeiria.ai.model import AIModelContentPart, AIModelMessage
from apeiria.app.ai.runtime.media import prepare_runtime_media_parts

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.session.context import RuntimeTurnSource


def project_media_into_messages(
    messages: tuple[AIModelMessage, ...],
    *,
    source: "RuntimeTurnSource",
) -> tuple[tuple[AIModelMessage, ...], dict[str, object]]:
    """Attach source media to the current user model message."""

    if not source.media_parts:
        return messages, {}

    target_index = _last_user_message_index(messages)
    if target_index is None:
        return messages, _diagnostics(source=source, projected=False)

    prepared = prepare_runtime_media_parts(source.media_parts)
    target = messages[target_index]
    fallback_text = _content_with_fallbacks(target.content, source=source)
    parts: list[AIModelContentPart] = []
    if fallback_text:
        parts.append(AIModelContentPart(kind="text", text=fallback_text))
    parts.extend(prepared.parts)

    if not prepared.parts:
        return messages, _diagnostics(
            source=source,
            projected=False,
            preparation_diagnostics=prepared.diagnostics,
        )

    projected = list(messages)
    projected[target_index] = replace(
        target,
        content=fallback_text,
        parts=tuple(parts),
    )
    return tuple(projected), _diagnostics(
        source=source,
        projected=True,
        preparation_diagnostics=prepared.diagnostics,
    )


def _last_user_message_index(messages: tuple[AIModelMessage, ...]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            return index
    return None


def _content_with_fallbacks(
    content: str,
    *,
    source: "RuntimeTurnSource",
) -> str:
    items = [content.strip()] if content.strip() else []
    for media_part in source.media_parts:
        if media_part.fallback_text and media_part.fallback_text not in items:
            items.append(media_part.fallback_text)
    return "\n".join(items)


def _diagnostics(
    *,
    source: "RuntimeTurnSource",
    projected: bool,
    preparation_diagnostics: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    counts: dict[str, int] = {}
    required_count = 0
    optional_count = 0
    for media_part in source.media_parts:
        counts[media_part.kind] = counts.get(media_part.kind, 0) + 1
        if media_part.required:
            required_count += 1
        else:
            optional_count += 1
    return {
        "multimodal": {
            "projected": projected,
            "media_counts": counts,
            "required_media_count": required_count,
            "optional_media_count": optional_count,
            "preparation": list(preparation_diagnostics),
        },
        "media_counts": counts,
    }


__all__ = ["project_media_into_messages"]
