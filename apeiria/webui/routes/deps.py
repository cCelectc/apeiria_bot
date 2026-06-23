from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request

from apeiria.db.engine import get_session
from apeiria.runtime.context import get_current_runtime

_RUNTIME_UNAVAILABLE_DETAIL = "Apeiria runtime control plane is unavailable."

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncIterator["AsyncSession"]:
    async with get_session() as db:
        yield db


def _request_is_secure(request: Request | None) -> bool:
    if request is None:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.split(",", 1)[0].strip().lower() == "https":
        return True
    return request.url.scheme == "https"


def require_runtime_control_plane() -> Any:
    runtime = get_current_runtime()
    if runtime is None or runtime.control_plane is None:
        raise HTTPException(
            status_code=503,
            detail=_RUNTIME_UNAVAILABLE_DETAIL,
        )
    return runtime.control_plane
