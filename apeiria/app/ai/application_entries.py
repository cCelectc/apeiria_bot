"""Lazy wiring helpers for AI application entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

EntryT = TypeVar("EntryT")


@dataclass(slots=True)
class LazyApplicationEntry(Generic[EntryT]):
    """Defer loading a focused application entry until it is used."""

    factory: "Callable[[], EntryT]"
    _entry: EntryT | None = field(default=None, init=False, repr=False)

    def resolve(self) -> EntryT:
        if self._entry is None:
            self._entry = self.factory()
        return self._entry


__all__ = ["LazyApplicationEntry"]
