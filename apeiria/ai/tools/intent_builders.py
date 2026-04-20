"""Helpers for building structured tool intents."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolIntent


def build_capability_intents(message_text: str) -> list["AIToolIntent"]:
    """Build capability intents for the current message."""

    from apeiria.ai.tools.models import (
        AINoneBotCapabilityRequest,
        AIPluginInspectCapabilityInput,
        AIToolIntent,
    )

    intents: list[AIToolIntent] = []
    lowered = message_text.lower()

    if any(token in lowered for token in ("help", "帮助")):
        intents.append(
            AIToolIntent(
                tool_name="plugin.capability",
                kind="invoke_capability",
                input_payload=AINoneBotCapabilityRequest(
                    capability_name="help.show",
                    arguments={},
                ),
                reason="help-related keyword detected",
            )
        )

    if any(token in lowered for token in ("plugin", "插件", "inspect")):
        intents.append(
            AIToolIntent(
                tool_name="plugin.capability",
                kind="invoke_capability",
                input_payload=AINoneBotCapabilityRequest(
                    capability_name="plugin.inspect",
                    arguments=AIPluginInspectCapabilityInput(
                        plugin_query=message_text,
                    ).__dict__,
                ),
                reason="plugin inspection keyword detected",
            )
        )

    return intents
