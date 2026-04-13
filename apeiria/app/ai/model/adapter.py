"""Adapter contracts for AI model execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AIModelToolDefinition:
    """One function-calling tool definition exposed to a model source adapter."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class AIModelToolCall:
    """One tool call returned by a model source adapter."""

    tool_call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AIModelCatalogItem:
    """One source-reported model catalog item."""

    id: str
    name: str


@dataclass(frozen=True)
class AIModelGenerateRequest:
    """Unified text generation request for Apeiria AI services."""

    source_id: str
    model_name: str
    prompt: str
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[AIModelToolDefinition, ...] = ()
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelGenerateResponse:
    """Unified text generation response for Apeiria AI services."""

    source_id: str
    model_name: str
    content: str
    tool_calls: tuple[AIModelToolCall, ...] = ()
    raw: dict[str, Any] | None = None


class AIModelAdapter(Protocol):
    """Source adapter protocol for Apeiria model execution."""

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]: ...

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse: ...
