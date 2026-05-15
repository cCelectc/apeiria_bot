"""Deterministic identity helpers for retrieval projections."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedCapabilityModel


def retrieval_document_id(*, domain: str, source_id: str) -> str:
    """Return a stable retrieval document id for one domain object."""

    normalized_domain = domain.strip().lower()
    normalized_source = source_id.strip()
    return f"{normalized_domain}:{normalized_source}"


def content_hash_for_text(*texts: str | None) -> str:
    """Return a deterministic content hash for retrieval-index freshness."""

    digest = hashlib.sha256()
    for text in texts:
        digest.update((text or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def embedding_space_id_for_selected(
    selected: "AISelectedCapabilityModel",
    *,
    dimension: int,
) -> str:
    """Return a deterministic embedding-space id for comparable vectors."""

    source = selected.source
    model = selected.model
    adapter_kind = source.adapter_kind or source.client_type
    payload = {
        "adapter_kind": adapter_kind,
        "dimension": dimension,
        "model_identifier": model.model_identifier,
        "normalization_or_version": _normalization_or_version(selected),
        "source_id": source.source_id,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return "embspace_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def embedding_space_label(
    selected: "AISelectedCapabilityModel",
    *,
    dimension: int,
) -> str:
    """Return a compact readable label for diagnostics and admin display."""

    source = selected.source
    adapter_kind = source.adapter_kind or source.client_type
    parts = (
        adapter_kind,
        source.source_id,
        selected.model.model_identifier,
        str(dimension),
    )
    return ":".join(parts)


def _normalization_or_version(selected: "AISelectedCapabilityModel") -> str:
    metadata = getattr(selected.model, "capability_metadata", None) or {}
    options = getattr(selected.model, "default_options", None) or {}
    normalization = metadata.get("normalization") or options.get("normalization")
    revision = metadata.get("revision") or metadata.get("version")
    if normalization is not None or revision is not None:
        return f"norm={normalization or 'default'};rev={revision or 'default'}"
    return "default"
