"""Active AI runtime invocation surface contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class RuntimeTraceContext:
    """Bounded labels supplied by runtime surface entrypoints."""

    kind: str
    trigger: str


@dataclass(frozen=True, slots=True)
class FutureTaskRuntimeResult:
    """Runtime outcome returned to durable future-task execution."""

    reply_text: str
    commit_status: str = "committed"
    delivery_status: str | None = None
    substeps: "Mapping[str, str]" = field(default_factory=dict)
    diagnostics: "Mapping[str, object]" = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "substeps", _read_only_mapping(self.substeps))
        object.__setattr__(
            self,
            "diagnostics",
            _read_only_mapping(self.diagnostics),
        )


def _read_only_mapping(value: "Mapping[str, object]") -> MappingProxyType[str, object]:
    return MappingProxyType(dict(value))


__all__ = ["FutureTaskRuntimeResult", "RuntimeTraceContext"]
