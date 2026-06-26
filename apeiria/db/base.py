from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class ISOTimestampMixin:
    created_at: Mapped[str] = mapped_column(String, default=_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String, default=_now_iso, onupdate=_now_iso, nullable=False
    )
