"""GroupConsole model — per-group configuration."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class GroupConsole(Model):
    """Per-group configuration and status."""

    __tablename__ = "group_console"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    group_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    group_level: Mapped[int] = mapped_column(default=0)
    disabled_plugins: Mapped[str] = mapped_column(Text, default="[]")
    bot_status: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(), onupdate=func.now()
    )
