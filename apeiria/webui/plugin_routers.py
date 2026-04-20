"""Cross-plugin HTTP router registry.

Plugins register their own APIRouter via :func:`register_plugin_router` at
plugin import time. The Web UI host then includes all registered routers
when FastAPI starts. This keeps plugin-provided HTTP surfaces lifecycle-
aligned with the plugin itself — disable the plugin and its routes vanish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


@dataclass(frozen=True)
class PluginRouterBinding:
    """One plugin-owned APIRouter scheduled for inclusion by the Web UI host."""

    prefix: str
    router: APIRouter
    tags: tuple[str, ...] = ()


_BINDINGS: list[PluginRouterBinding] = []


def register_plugin_router(
    prefix: str,
    router: APIRouter,
    *,
    tags: tuple[str, ...] = (),
) -> None:
    """Register a plugin-owned APIRouter for later inclusion."""
    _BINDINGS.append(PluginRouterBinding(prefix=prefix, router=router, tags=tags))


def iter_plugin_routers() -> tuple[PluginRouterBinding, ...]:
    """Return all registered plugin router bindings."""
    return tuple(_BINDINGS)
