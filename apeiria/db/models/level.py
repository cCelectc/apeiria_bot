"""LevelUser model — per-user-per-group permission level."""

from __future__ import annotations

from nonebot_plugin_orm import Model
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class LevelUser(Model):
    """Per-user-per-group permission level (0-6)."""

    __tablename__ = "level_user"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_level_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[int] = mapped_column(default=0)
