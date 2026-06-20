from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class ISOTimestampMixin:
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, default=_now_iso, onupdate=_now_iso)
