"""HTTP route modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter

    router: APIRouter

__all__ = ["router"]


def __getattr__(name: str):
    if name == "router":
        from .router import router

        return router
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
