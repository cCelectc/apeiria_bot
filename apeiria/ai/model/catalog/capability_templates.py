"""Local capability enrichment templates for source-backed models."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from apeiria.ai.model.runtime.capabilities import (
    AIModelAdapterKind,
    capabilities_to_metadata,
)
from apeiria.ai.model.runtime.capability_sources import (
    CapabilityFactLayer,
    CapabilityFactMergeResult,
    merge_capability_fact_layers,
    parse_capability_provenance,
)
from apeiria.ai.model.runtime.registry import provider_adapter_registry
from apeiria.ai.model.sources.models import resolve_adapter_kind_for_client_type

if TYPE_CHECKING:
    from apeiria.ai.model.sources.models import AISourceDefinition


@dataclass(frozen=True)
class ModelCapabilityTemplate:
    """One deterministic local model capability template."""

    template_id: str
    adapter_kind: AIModelAdapterKind
    identifier_patterns: tuple[str, ...]
    priority: int
    source_hints: tuple[str, ...] = ()
    capability_metadata: dict[str, object] = field(default_factory=dict)
    default_options: dict[str, object] = field(default_factory=dict)
    confidence: str = "inferred"
    detail: str | None = None

    def matches(
        self,
        *,
        adapter_kind: str,
        model_identifier: str,
        source_hints: tuple[str, ...],
    ) -> bool:
        if adapter_kind != self.adapter_kind:
            return False
        normalized_identifier = model_identifier.strip().lower()
        if not normalized_identifier:
            return False
        if self.source_hints:
            normalized_hints = {item.strip().lower() for item in source_hints if item}
            required_hints = {item.strip().lower() for item in self.source_hints}
            if normalized_hints.isdisjoint(required_hints):
                return False
        return any(
            fnmatchcase(normalized_identifier, pattern.strip().lower())
            for pattern in self.identifier_patterns
        )

    def to_layer(self) -> CapabilityFactLayer:
        return CapabilityFactLayer(
            source="model_template",
            confidence=self.confidence,  # type: ignore[arg-type]
            capability_metadata=dict(self.capability_metadata),
            default_options=dict(self.default_options),
            detail=self.detail or self.template_id,
        )


class ModelCapabilityTemplateRegistry:
    """In-memory registry for local source-model capability templates."""

    def __init__(self, templates: tuple[ModelCapabilityTemplate, ...] = ()) -> None:
        self._templates = tuple(templates)

    def select(
        self,
        *,
        adapter_kind: str,
        model_identifier: str,
        source_hints: tuple[str, ...],
    ) -> ModelCapabilityTemplate | None:
        matches = [
            item
            for item in self._templates
            if item.matches(
                adapter_kind=adapter_kind,
                model_identifier=model_identifier,
                source_hints=source_hints,
            )
        ]
        if not matches:
            return None
        return sorted(
            matches,
            key=lambda item: (-item.priority, item.template_id),
        )[0]


def enrich_model_capabilities(  # noqa: PLR0913
    *,
    source: "AISourceDefinition",
    model_identifier: str,
    registry: ModelCapabilityTemplateRegistry | None = None,
    upstream_capability_metadata: dict[str, object] | None = None,
    upstream_default_options: dict[str, object] | None = None,
    owner_capability_metadata: dict[str, object] | None = None,
    owner_default_options: dict[str, object] | None = None,
    existing_provenance: dict[str, object] | None = None,
) -> CapabilityFactMergeResult:
    """Build effective capability metadata and provenance for one source model."""

    registry = registry or model_capability_template_registry
    adapter_kind = source.adapter_kind or resolve_adapter_kind_for_client_type(
        source.client_type
    )
    adapter_entry = provider_adapter_registry.get(adapter_kind)
    template = registry.select(
        adapter_kind=adapter_kind,
        model_identifier=model_identifier,
        source_hints=_source_hints(source),
    )
    layers = [
        CapabilityFactLayer(
            source="adapter_default",
            confidence="default",
            capability_metadata=capabilities_to_metadata(
                adapter_entry.default_capabilities
            ),
            detail=adapter_entry.display_name,
        ),
        CapabilityFactLayer(
            source="preset_template",
            confidence="default",
            capability_metadata=dict(source.capability_metadata or {}),
            default_options=dict(source.default_options or {}),
            detail=f"source preset {source.preset_type}",
        ),
    ]
    layers.append(
        template.to_layer() if template is not None else _conservative_layer()
    )
    if upstream_capability_metadata or upstream_default_options:
        layers.append(
            CapabilityFactLayer(
                source="upstream_catalog",
                confidence="reported",
                capability_metadata=dict(upstream_capability_metadata or {}),
                default_options=dict(upstream_default_options or {}),
                detail="provider catalog",
            )
        )
    if owner_capability_metadata or owner_default_options:
        layers.append(
            CapabilityFactLayer(
                source="owner_override",
                confidence="owner",
                capability_metadata=dict(owner_capability_metadata or {}),
                default_options=dict(owner_default_options or {}),
                detail="owner supplied value",
            )
        )
    return merge_capability_fact_layers(
        *layers,
        existing_provenance=parse_capability_provenance(existing_provenance),
    )


def enrich_catalog_item(
    *,
    source: "AISourceDefinition",
    catalog_item: object,
    registry: ModelCapabilityTemplateRegistry | None = None,
) -> CapabilityFactMergeResult:
    """Enrich one adapter-returned catalog item with local and upstream facts."""

    return enrich_model_capabilities(
        source=source,
        model_identifier=str(getattr(catalog_item, "id", "")),
        registry=registry,
        upstream_capability_metadata=_dict_attr(catalog_item, "capability_metadata"),
        upstream_default_options=_dict_attr(catalog_item, "default_options"),
        existing_provenance=_dict_attr(catalog_item, "capability_provenance"),
    )


def _dict_attr(item: object, attr: str) -> dict[str, object]:
    value = getattr(item, attr, None)
    return dict(value) if isinstance(value, dict) else {}


def _source_hints(source: "AISourceDefinition") -> tuple[str, ...]:
    hints = [
        source.preset_type,
        source.name,
        source.api_base or "",
        source.adapter_kind or "",
    ]
    return tuple(item.lower() for item in hints if item)


def _conservative_layer() -> CapabilityFactLayer:
    return CapabilityFactLayer(
        source="preset_template",
        confidence="default",
        capability_metadata={
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "tool_calling": False,
            "reasoning": {"supported": False},
            "structured_output": {"supported": False},
            "json_mode": False,
            "streaming": False,
        },
        detail="conservative source-model default",
    )


model_capability_template_registry = ModelCapabilityTemplateRegistry()
