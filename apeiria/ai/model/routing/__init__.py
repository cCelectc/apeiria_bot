"""AI model routing boundary."""

from __future__ import annotations

from .bindings import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    resolve_model_binding,
)
from .models import AIModelProfileDefinition, AIModelRouteQuery, AIModelTaskClass
from .rules import list_model_profile_candidates, resolve_model_profile
from .selection import (
    AISelectedCapabilityModel,
    AISelectedModel,
    resolve_capability_selected_model,
    resolve_implicit_selected_model,
    resolve_source_selected_model_with_fallback,
    select_source_for_profile,
)

__all__ = [
    "AIModelBindingSpec",
    "AIModelBindingTarget",
    "AIModelProfileDefinition",
    "AIModelRouteQuery",
    "AIModelTaskClass",
    "AISelectedCapabilityModel",
    "AISelectedModel",
    "list_model_profile_candidates",
    "resolve_capability_selected_model",
    "resolve_implicit_selected_model",
    "resolve_model_binding",
    "resolve_model_profile",
    "resolve_source_selected_model_with_fallback",
    "select_source_for_profile",
]
