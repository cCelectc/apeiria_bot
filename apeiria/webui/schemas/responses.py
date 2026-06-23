"""Unified API response models."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard success wrapper for all API endpoints."""

    data: T


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""

    items: list[T]
    total: int
    page: int
    page_size: int


class ApiError(BaseModel):
    """Standard error response."""

    code: str
    message: str
    details: dict[str, list[str]] | None = None


def ok(data: T) -> dict[str, T]:
    """Wrap a value in the standard success envelope."""
    return {"data": data}


def paginated(
    items: list[T], total: int, page: int, page_size: int
) -> dict[str, object]:
    """Wrap paginated results in the standard envelope."""
    return {
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    }
