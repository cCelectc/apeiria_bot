"""SchemaMeta model — tracks Apeiria database schema state."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class SchemaMeta(Model):
    """Schema version state for Apeiria-managed database tables."""

    __tablename__ = "apeiria_schema_meta"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schema_version: Mapped[int] = mapped_column(default=1)
    initialized_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
