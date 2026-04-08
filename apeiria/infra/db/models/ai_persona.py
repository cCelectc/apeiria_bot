"""AIPersona model — persisted persona definitions."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AIPersona(Model):
    """One persisted persona definition."""

    __tablename__ = "ai_persona"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text)
    style_prompt: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
