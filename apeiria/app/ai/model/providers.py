"""Provider registry domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AIProviderType = Literal[
    "openai_compatible",
    "anthropic",
    "anthropic_compatible",
    "gemini",
    "ollama",
    "litellm",
    "agent_runner",
]


@dataclass(frozen=True)
class AIProviderDefinition:
    """One configured upstream provider."""

    provider_id: str
    name: str
    provider_type: AIProviderType
    api_base: str | None
    api_key_env_name: str | None = None
    enabled: bool = True
    default_model: str | None = None
