"""CommandStatistics model — command usage tracking."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column


class CommandStatistics(Model):
    """Records each command invocation for analytics."""

    __tablename__ = "command_statistics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plugin_name: Mapped[str] = mapped_column(String(256), index=True)
    command: Mapped[str] = mapped_column(String(256))
    user_id: Mapped[str] = mapped_column(String(64))
    group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    called_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    success: Mapped[bool] = mapped_column(default=True)
