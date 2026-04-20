"""Formal plugin metadata contract objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.plugins.metadata.api import RegisterConfig


@dataclass(frozen=True)
class ConfigNamespaceContract:
    """Plugin config namespace contract consumed by governance services."""

    namespace: str
    owner_kind: str
    owner_id: str
    source: str
    legacy_flatten: bool
    has_config_model: bool
    configs: list["RegisterConfig"] = field(default_factory=list)
    scope_support: tuple[str, ...] = ("project",)
    mutation_modes: tuple[str, ...] = (
        "structured_patch",
        "raw_replace",
        "raw_validate",
        "clear_keys",
    )
