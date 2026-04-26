"""Shared operation result schemas."""

from __future__ import annotations

from pydantic import BaseModel


class OperationStatusResponse(BaseModel):
    status: str = "ok"
    detail: str | None = None
