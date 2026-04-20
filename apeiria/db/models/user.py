"""UserConsole model — global user data."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column


class UserConsole(Model):
    """Global user data, shared across groups."""

    __tablename__ = "user_console"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gold: Mapped[int] = mapped_column(default=0)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(), onupdate=func.now()
    )
