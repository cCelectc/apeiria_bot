"""Runtime-level handler registry populated from native plugin sync."""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apeiria.app.plugins.models import HandlerDescriptor


class HandlerRegistry:
    """Store of formal `HandlerDescriptor` objects projected from matchers."""

    def __init__(self) -> None:
        self._handlers: dict[str, HandlerDescriptor] = {}
        self._lock = RLock()

    def register(self, descriptor: "HandlerDescriptor") -> None:
        with self._lock:
            self._handlers[descriptor.handler_id] = descriptor

    def register_many(self, descriptors: "Iterable[HandlerDescriptor]") -> None:
        with self._lock:
            for descriptor in descriptors:
                self._handlers[descriptor.handler_id] = descriptor

    def replace_for_plugin(
        self,
        plugin_module: str,
        descriptors: "Iterable[HandlerDescriptor]",
    ) -> None:
        """Drop all descriptors for ``plugin_module`` and replace with the new set."""

        with self._lock:
            self._handlers = {
                handler_id: descriptor
                for handler_id, descriptor in self._handlers.items()
                if descriptor.plugin_module != plugin_module
            }
            for descriptor in descriptors:
                self._handlers[descriptor.handler_id] = descriptor

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()

    def all(self) -> tuple["HandlerDescriptor", ...]:
        with self._lock:
            return tuple(self._handlers.values())

    def by_plugin(self, plugin_module: str) -> tuple["HandlerDescriptor", ...]:
        with self._lock:
            return tuple(
                descriptor
                for descriptor in self._handlers.values()
                if descriptor.plugin_module == plugin_module
            )

    def get(self, handler_id: str) -> "HandlerDescriptor | None":
        with self._lock:
            return self._handlers.get(handler_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._handlers)


handler_registry = HandlerRegistry()
