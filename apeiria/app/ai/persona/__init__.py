"""Persona registry and binding resolution for the AI domain."""

from .models import (
    AIPersonaBindingSpec,
    AIPersonaBindingTarget,
    AIPersonaDefinition,
    PersonaBindingScope,
)
from .resolver import resolve_persona_binding

__all__ = [
    "AIPersonaBindingSpec",
    "AIPersonaBindingTarget",
    "AIPersonaDefinition",
    "PersonaBindingScope",
    "resolve_persona_binding",
]
