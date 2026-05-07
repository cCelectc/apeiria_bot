"""Capability projection diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AICapabilityExposureDiagnostics:
    """Bounded facts emitted with one exposure plan."""

    total_contracts: int
    visible_tools: int
    prompt_activations: int
    hidden_count: int
    denied_count: int
    unavailable_count: int
    model_supports_tools: bool
