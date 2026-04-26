"""Persona registry package with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIPersonaBindingSpec,
    AIPersonaBindingTarget,
    AIPersonaCreateInput,
    AIPersonaDefinition,
)
from .resolver import resolve_persona_binding

if TYPE_CHECKING:
    from .service import (
        AIPersonaPromptBundle,
        AIPersonaRenderContext,
        AIPersonaService,
        ai_persona_service,
        build_persona_render_context,
    )

__all__ = [
    "AIPersonaBindingSpec",
    "AIPersonaBindingTarget",
    "AIPersonaCreateInput",
    "AIPersonaDefinition",
    "AIPersonaPromptBundle",
    "AIPersonaRenderContext",
    "AIPersonaService",
    "ai_persona_service",
    "build_persona_render_context",
    "resolve_persona_binding",
]

_LAZY_EXPORTS = {
    "AIPersonaPromptBundle": ".service",
    "AIPersonaRenderContext": ".service",
    "AIPersonaService": ".service",
    "ai_persona_service": ".service",
    "build_persona_render_context": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
