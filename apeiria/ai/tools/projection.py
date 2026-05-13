"""Provider-specific projection for provider-neutral AI tools."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolDefinition

ProviderToolKind = Literal["openai", "anthropic", "gemini"]


@dataclass(frozen=True)
class AIToolProviderProjection:
    """Provider payloads plus explicit provider-name to stable-name mapping."""

    provider: ProviderToolKind
    payloads: tuple[dict[str, Any], ...]
    name_map: dict[str, str]

    def resolve_provider_name(self, provider_name: str) -> str | None:
        return self.name_map.get(provider_name)


def project_tools_for_openai(
    tools: tuple["AIToolDefinition", ...],
) -> AIToolProviderProjection:
    """Project tools to OpenAI-compatible function tool payloads."""

    names = build_provider_name_map(tools)
    return AIToolProviderProjection(
        provider="openai",
        name_map=names,
        payloads=tuple(
            {
                "type": "function",
                "function": {
                    "name": provider_name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                    "strict": True,
                },
            }
            for provider_name, tool in _iter_projected_tools(names, tools)
        ),
    )


def project_tools_for_anthropic(
    tools: tuple["AIToolDefinition", ...],
) -> AIToolProviderProjection:
    """Project tools to Anthropic-compatible tool payloads."""

    names = build_provider_name_map(tools)
    return AIToolProviderProjection(
        provider="anthropic",
        name_map=names,
        payloads=tuple(
            {
                "name": provider_name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for provider_name, tool in _iter_projected_tools(names, tools)
        ),
    )


def project_tools_for_gemini(
    tools: tuple["AIToolDefinition", ...],
) -> AIToolProviderProjection:
    """Project tools to Gemini-native function declarations."""

    names = build_provider_name_map(tools)
    return AIToolProviderProjection(
        provider="gemini",
        name_map=names,
        payloads=tuple(
            {
                "name": provider_name,
                "description": tool.description,
                "parameters": tool.input_schema,
            }
            for provider_name, tool in _iter_projected_tools(names, tools)
        ),
    )


def build_provider_name_map(
    tools: tuple["AIToolDefinition", ...],
) -> dict[str, str]:
    """Return provider-safe names mapped to stable tool names."""

    used: set[str] = set()
    mapping: dict[str, str] = {}
    for tool in tools:
        provider_name = _provider_safe_tool_name(tool.name)
        if provider_name in used:
            provider_name = f"{provider_name}_{_stable_suffix(tool.name)}"
        used.add(provider_name)
        mapping[provider_name] = tool.name
    return mapping


def _iter_projected_tools(
    name_map: dict[str, str],
    tools: tuple["AIToolDefinition", ...],
) -> tuple[tuple[str, "AIToolDefinition"], ...]:
    by_name = {tool.name: tool for tool in tools}
    return tuple(
        (provider_name, by_name[tool_name])
        for provider_name, tool_name in name_map.items()
    )


def _provider_safe_tool_name(tool_name: str) -> str:
    safe = _PROVIDER_SAFE_NAME_RE.sub("_", tool_name).strip("_")
    if not safe:
        safe = "tool"
    if safe[0].isdigit():
        safe = f"tool_{safe}"
    return safe[:64]


def _stable_suffix(tool_name: str) -> str:
    return hashlib.sha1(tool_name.encode("utf-8")).hexdigest()[:8]


_PROVIDER_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_]")


__all__ = [
    "AIToolProviderProjection",
    "ProviderToolKind",
    "build_provider_name_map",
    "project_tools_for_anthropic",
    "project_tools_for_gemini",
    "project_tools_for_openai",
]
