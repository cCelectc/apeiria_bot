"""Shared source model domain models for admin-managed providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AISourceModelDefinition:
    """One configured source model under one AI source."""

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIChatModelDefinition(AISourceModelDefinition):
    """One configured chat model under one AI source."""


@dataclass(frozen=True)
class AIEmbeddingModelDefinition(AISourceModelDefinition):
    """One configured embedding model under one AI source."""


@dataclass(frozen=True)
class AISpeechToTextModelDefinition(AISourceModelDefinition):
    """One configured STT model under one AI source."""


@dataclass(frozen=True)
class AITextToSpeechModelDefinition(AISourceModelDefinition):
    """One configured TTS model under one AI source."""


@dataclass(frozen=True)
class AIRerankModelDefinition(AISourceModelDefinition):
    """One configured rerank model under one AI source."""
