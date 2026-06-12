"""SQLAlchemy declarative base and shared mixins."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class TimestampMixin:
    """Unified timestamp mixin using INTEGER millisecond epoch.

    Millisecond precision eliminates same-second ordering ties,
    removing the need for an INTEGER id tiebreaker column.
    """

    created_at: Mapped[int] = mapped_column(Integer, default=_epoch_ms)
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )
