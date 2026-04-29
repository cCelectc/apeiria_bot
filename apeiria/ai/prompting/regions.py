"""Prompt region projection helpers."""

from __future__ import annotations

from collections.abc import Iterable  # noqa: TC003
from dataclasses import dataclass
from typing import Literal

from .models import PromptPacket, PromptPurpose, PromptSection

PromptRegion = Literal["stable", "dynamic"]


@dataclass(frozen=True, slots=True)
class PromptRegionProjection:
    """Machine-readable stable and dynamic prompt sections."""

    purpose: PromptPurpose
    stable: tuple[PromptSection, ...]
    dynamic: tuple[PromptSection, ...]

    @property
    def sections(self) -> tuple[PromptSection, ...]:
        """Return sections in render order: stable prefix, then dynamic turn data."""

        return (*self.stable, *self.dynamic)

    def to_packet(self) -> PromptPacket:
        """Convert the projection back to the provider-neutral packet shape."""

        return PromptPacket(purpose=self.purpose, sections=self.sections)


def project_prompt_regions(
    packet: PromptPacket,
    *,
    stable_section_names: Iterable[str],
) -> PromptRegionProjection:
    """Project packet sections into cacheable stable and dynamic regions."""

    stable_names = set(stable_section_names)
    stable: list[PromptSection] = []
    dynamic: list[PromptSection] = []
    for section in packet.sections:
        if section.name in stable_names:
            stable.append(section)
        else:
            dynamic.append(section)
    return PromptRegionProjection(
        purpose=packet.purpose,
        stable=tuple(stable),
        dynamic=tuple(dynamic),
    )


def prompt_region_diagnostics(
    projection: PromptRegionProjection,
) -> dict[str, object]:
    """Return bounded prompt-region metadata without section content."""

    return {
        "prompt_purpose": projection.purpose,
        "stable_section_names": tuple(section.name for section in projection.stable),
        "dynamic_section_names": tuple(section.name for section in projection.dynamic),
        "stable_section_count": len(projection.stable),
        "dynamic_section_count": len(projection.dynamic),
        "total_section_count": len(projection.sections),
    }
