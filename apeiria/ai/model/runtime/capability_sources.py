"""Capability fact provenance and runtime observation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from apeiria.ai.turn_records import sanitize_model_diagnostic

CapabilityFactSource: TypeAlias = Literal[
    "adapter_default",
    "preset_template",
    "model_template",
    "upstream_catalog",
    "owner_override",
    "runtime_observation",
]
CapabilityFactConfidence: TypeAlias = Literal[
    "default",
    "inferred",
    "reported",
    "verified",
    "owner",
]

_FACT_SOURCES: frozenset[str] = frozenset(
    {
        "adapter_default",
        "preset_template",
        "model_template",
        "upstream_catalog",
        "owner_override",
        "runtime_observation",
    }
)
_CONFIDENCES: frozenset[str] = frozenset(
    {"default", "inferred", "reported", "verified", "owner"}
)
_UNSUPPORTED_MARKERS = (
    "not support",
    "not supported",
    "unsupported",
    "does not support",
    "is not available",
    "not available",
    "invalid parameter",
    "unknown parameter",
)


@dataclass(frozen=True)
class CapabilityFactProvenance:
    """Source and confidence for one capability or default-option field."""

    source: CapabilityFactSource
    confidence: CapabilityFactConfidence
    detail: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class CapabilityFactLayer:
    """One ordered patch to effective model capability metadata."""

    source: CapabilityFactSource
    confidence: CapabilityFactConfidence
    capability_metadata: dict[str, object] = field(default_factory=dict)
    default_options: dict[str, object] = field(default_factory=dict)
    detail: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class CapabilityFactMergeResult:
    """Effective capability metadata, options, and explainable provenance."""

    capability_metadata: dict[str, object]
    default_options: dict[str, object]
    provenance: dict[str, CapabilityFactProvenance]


@dataclass(frozen=True)
class AIModelCapabilityObservation:
    """Bounded diagnostic when provider behavior contradicts local facts."""

    planned_feature: str
    model_ref: str
    diagnostic: str
    source_fact: str | None = None
    suggested_correction: str = "review model capability metadata"

    def to_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "planned_feature": self.planned_feature,
            "model_ref": self.model_ref,
            "diagnostic": self.diagnostic,
            "suggested_correction": self.suggested_correction,
        }
        if self.source_fact:
            metadata["source_fact"] = self.source_fact
        return metadata


def parse_capability_provenance(
    raw: Any,
) -> dict[str, CapabilityFactProvenance]:
    """Parse JSON-like provenance into typed records, dropping bad entries."""

    if not isinstance(raw, dict):
        return {}
    parsed: dict[str, CapabilityFactProvenance] = {}
    for path, value in raw.items():
        if not isinstance(path, str) or not isinstance(value, dict):
            continue
        source = value.get("source")
        confidence = value.get("confidence")
        if source not in _FACT_SOURCES or confidence not in _CONFIDENCES:
            continue
        detail = value.get("detail")
        updated_at = value.get("updated_at")
        parsed[path] = CapabilityFactProvenance(
            source=source,  # type: ignore[arg-type]
            confidence=confidence,  # type: ignore[arg-type]
            detail=detail if isinstance(detail, str) and detail else None,
            updated_at=updated_at
            if isinstance(updated_at, str) and updated_at
            else None,
        )
    return parsed


def capability_provenance_to_metadata(
    provenance: dict[str, CapabilityFactProvenance] | None,
) -> dict[str, object]:
    """Serialize provenance records for storage and API responses."""

    if not provenance:
        return {}
    serialized: dict[str, object] = {}
    for path, item in sorted(provenance.items()):
        payload: dict[str, object] = {
            "source": item.source,
            "confidence": item.confidence,
        }
        if item.detail:
            payload["detail"] = item.detail
        if item.updated_at:
            payload["updated_at"] = item.updated_at
        serialized[path] = payload
    return serialized


def merge_capability_fact_layers(
    *layers: CapabilityFactLayer,
    existing_provenance: dict[str, CapabilityFactProvenance] | None = None,
) -> CapabilityFactMergeResult:
    """Merge ordered fact layers into effective capability metadata."""

    capability_metadata: dict[str, object] = {}
    default_options: dict[str, object] = {}
    provenance = dict(existing_provenance or {})
    supported_options: list[str] = []

    for layer in layers:
        if layer.source == "runtime_observation":
            continue
        fact = CapabilityFactProvenance(
            source=layer.source,
            confidence=layer.confidence,
            detail=layer.detail,
            updated_at=layer.updated_at,
        )
        for key, value in layer.capability_metadata.items():
            if key == "supported_options":
                supported_options = _merge_unique_strings(supported_options, value)
                capability_metadata[key] = supported_options
            else:
                capability_metadata[key] = value
            provenance[f"capability.{key}"] = fact
        for key, value in layer.default_options.items():
            default_options[key] = value
            provenance[f"option.{key}"] = fact

    return CapabilityFactMergeResult(
        capability_metadata=capability_metadata,
        default_options=default_options,
        provenance=provenance,
    )


def mark_owner_overrides(
    *,
    capability_metadata: dict[str, object] | None = None,
    default_options: dict[str, object] | None = None,
    existing: dict[str, CapabilityFactProvenance] | None = None,
    detail: str = "owner supplied value",
) -> dict[str, CapabilityFactProvenance]:
    """Mark supplied capability and option fields as owner overrides."""

    provenance = dict(existing or {})
    owner_fact = CapabilityFactProvenance(
        source="owner_override",
        confidence="owner",
        detail=detail,
    )
    for key in capability_metadata or {}:
        provenance[f"capability.{key}"] = owner_fact
    for key in default_options or {}:
        provenance[f"option.{key}"] = owner_fact
    return provenance


def classify_capability_mismatch(
    exc: BaseException,
    *,
    planned_feature: str,
    model_ref: str,
    source_fact: str | None = None,
) -> AIModelCapabilityObservation | None:
    """Return a bounded observation for recognizable unsupported-feature errors."""

    diagnostic = sanitize_model_diagnostic(str(exc))
    lowered = diagnostic.lower()
    if not any(marker in lowered for marker in _UNSUPPORTED_MARKERS):
        return None
    feature = _resolve_feature(planned_feature=planned_feature, diagnostic=lowered)
    return AIModelCapabilityObservation(
        planned_feature=feature,
        model_ref=model_ref,
        diagnostic=diagnostic,
        source_fact=source_fact,
    )


def _resolve_feature(*, planned_feature: str, diagnostic: str) -> str:
    if planned_feature and planned_feature != "unknown":
        return planned_feature
    feature = "request_option"
    if "tool" in diagnostic or "function" in diagnostic:
        feature = "tool_calling"
    elif "response_format" in diagnostic or "json schema" in diagnostic:
        feature = "structured_output"
    elif "reasoning" in diagnostic:
        feature = "reasoning"
    elif "stream" in diagnostic:
        feature = "streaming"
    elif any(item in diagnostic for item in ("image", "audio", "file")):
        feature = "modality"
    return feature


def _merge_unique_strings(current: list[str], value: object) -> list[str]:
    merged = list(current)
    candidates: list[str] = []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = [item for item in value if isinstance(item, str)]
    for candidate in candidates:
        if candidate not in merged:
            merged.append(candidate)
    return merged
