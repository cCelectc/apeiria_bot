"""AI model routing boundary."""

from __future__ import annotations

from .bindings import (
    AIModelBindingSpec,
    AIModelBindingTarget,
    resolve_model_binding,
    resolve_model_route_binding,
)
from .models import (
    AIModelProfileDefinition,
    AIModelRouteAlgorithm,
    AIModelRouteBindingSpec,
    AIModelRouteDefinition,
    AIModelRouteMemberDefinition,
    AIModelRouteMode,
    AIModelRouteQuery,
    AIModelRouteScopeType,
    AIModelTaskClass,
)
from .routes import (
    AIModelRouteBindingCreateInput,
    AIModelRouteCreateInput,
    AIModelRouteMemberCreateInput,
)
from .rules import list_model_profile_candidates, resolve_model_profile
from .selection import (
    AIModelAttemptPlan,
    AISelectedCapabilityModel,
    AISelectedModel,
    resolve_capability_selected_model,
    resolve_implicit_selected_model,
    resolve_model_route_attempt_plan,
    resolve_source_selected_model,
    resolve_source_selected_model_with_fallback,
    select_source_for_profile,
)

__all__ = [
    "AIModelAttemptPlan",
    "AIModelBindingSpec",
    "AIModelBindingTarget",
    "AIModelProfileDefinition",
    "AIModelRouteAlgorithm",
    "AIModelRouteBindingCreateInput",
    "AIModelRouteBindingSpec",
    "AIModelRouteCreateInput",
    "AIModelRouteDefinition",
    "AIModelRouteMemberCreateInput",
    "AIModelRouteMemberDefinition",
    "AIModelRouteMode",
    "AIModelRouteQuery",
    "AIModelRouteScopeType",
    "AIModelTaskClass",
    "AISelectedCapabilityModel",
    "AISelectedModel",
    "list_model_profile_candidates",
    "resolve_capability_selected_model",
    "resolve_implicit_selected_model",
    "resolve_model_binding",
    "resolve_model_profile",
    "resolve_model_route_attempt_plan",
    "resolve_model_route_binding",
    "resolve_source_selected_model",
    "resolve_source_selected_model_with_fallback",
    "select_source_for_profile",
]
