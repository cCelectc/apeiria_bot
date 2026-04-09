"""Helpers for building structured tool intents."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolIntent

_CAPABILITY_HELP_TOKENS = (
    "帮助",
    "help",
    "怎么用",
)
_PLUGIN_INSPECT_PATTERNS = (
    "怎么用",
    "插件",
)


def build_capability_intents(
    *,
    tool_name: str,
    message_text: str,
) -> list["AIToolIntent"]:
    """Build capability intents for the current message."""

    from apeiria.app.ai.tools.models import (
        AINoneBotCapabilityRequest,
        AIPluginInspectCapabilityInput,
        AIToolIntent,
    )

    intents: list[AIToolIntent] = []
    normalized = message_text.lower()

    if _contains_any(normalized, _CAPABILITY_HELP_TOKENS):
        intents.append(
            AIToolIntent(
                tool_name=tool_name,
                kind="invoke_capability",
                input_payload=AINoneBotCapabilityRequest(
                    capability_name="help.show",
                    arguments={"topic": "plugins"},
                ),
            )
        )

    plugin_query = _extract_plugin_query(message_text)
    if plugin_query:
        intents.append(
            AIToolIntent(
                tool_name=tool_name,
                kind="invoke_capability",
                input_payload=AINoneBotCapabilityRequest(
                    capability_name="plugin.inspect",
                    arguments=AIPluginInspectCapabilityInput(
                        plugin_query=plugin_query,
                    ).__dict__,
                ),
            )
        )

    return intents


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _extract_plugin_query(text: str) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None
    if "怎么用" in normalized:
        query = normalized.split("怎么用", 1)[0].strip(" ，。！？!?")
        return _normalize_plugin_query(query)
    if "插件" in normalized and _contains_any(normalized, _PLUGIN_INSPECT_PATTERNS):
        query = normalized.split("插件", 1)[0].strip(" ，。！？!?")
        return _normalize_plugin_query(query)
    return None


def _normalize_plugin_query(query: str) -> str | None:
    normalized = query.strip()
    if not normalized:
        return None
    if normalized in {"帮助", "help", "帮我看看帮助"}:
        return None
    if normalized.startswith("帮我看看"):
        normalized = normalized.removeprefix("帮我看看").strip()
    return normalized or None
