"""Persona registry package."""

from __future__ import annotations

from .models import (
    AIPersonaBindingSpec,
    AIPersonaBindingTarget,
    AIPersonaCreateInput,
    AIPersonaDefinition,
)
from .resolver import resolve_persona_binding
from .service import (
    AIPersonaPromptBundle,
    AIPersonaRenderContext,
    AIPersonaService,
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
    "build_persona_render_context",
    "resolve_persona_binding",
]
