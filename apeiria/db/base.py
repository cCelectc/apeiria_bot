"""Shared SQLAlchemy base for Apeiria-managed tables."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for Apeiria-managed SQLite tables."""

