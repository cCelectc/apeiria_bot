from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from apeiria.runtime.context import get_current_runtime

_RUNTIME_UNAVAILABLE_DETAIL = "Apeiria runtime control plane is unavailable."


def require_runtime_control_plane() -> Any:
    runtime = get_current_runtime()
    if runtime is None or runtime.control_plane is None:
        raise HTTPException(
            status_code=503,
            detail=_RUNTIME_UNAVAILABLE_DETAIL,
        )
    return runtime.control_plane
