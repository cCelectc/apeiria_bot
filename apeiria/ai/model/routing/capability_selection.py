"""Capability-oriented default source/model selection service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.catalog.registry import SOURCE_MODEL_CAPABILITY_REGISTRY
from apeiria.ai.model.routing.selection import (
    AISelectedCapabilityModel,
    resolve_capability_selected_model,
)
from apeiria.ai.model.sources.service import ai_source_service

if TYPE_CHECKING:
    from apeiria.ai.model.sources.models import AISourceCapabilityType


class AIModelCapabilitySelectionService:
    """Select a default source/model pair for one capability type."""

    async def select_default_model(
        self,
        *,
        capability_type: "AISourceCapabilityType",
        preferred_source_id: str | None = None,
    ) -> AISelectedCapabilityModel | None:
        entry = SOURCE_MODEL_CAPABILITY_REGISTRY[capability_type]
        sources = await ai_source_service.list_sources()
        source_models = []
        for source in sources:
            if source.capability_type != capability_type or not source.enabled:
                continue
            source_models.extend(await entry.list_models(source.source_id))
        return resolve_capability_selected_model(
            sources,
            source_models,
            capability_type=capability_type,
            preferred_source_id=preferred_source_id,
        )


ai_model_capability_selection_service = AIModelCapabilitySelectionService()
