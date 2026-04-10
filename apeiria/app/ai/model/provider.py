"""Provider abstraction for AI model execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AIProviderModelItem:
    """One provider-reported model item."""

    id: str
    name: str


@dataclass(frozen=True)
class AIModelGenerateRequest:
    """Unified text generation request for Apeiria AI services."""

    provider_id: str
    model_name: str
    prompt: str
    temperature: float | None = None
    max_tokens: int | None = None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelGenerateResponse:
    """Unified text generation response for Apeiria AI services."""

    provider_id: str
    model_name: str
    content: str
    raw: dict[str, Any] | None = None


class AIModelProvider(Protocol):
    """Provider adapter protocol for Apeiria model execution."""

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIProviderModelItem]:
        ...

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        ...
