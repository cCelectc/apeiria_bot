from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_suppress_recording = contextvars.ContextVar("_suppress_recording", default=False)


@asynccontextmanager
async def suppress_send_recording() -> AsyncIterator[None]:
    _suppress_recording.set(True)
    try:
        yield
    finally:
        _suppress_recording.set(False)


def is_recording_suppressed() -> bool:
    return _suppress_recording.get()
