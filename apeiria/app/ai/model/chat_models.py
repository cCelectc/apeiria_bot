"""Chat model domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIChatModelDefinition:
    """One configured chat model under one AI source."""

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, Any] | None = None
