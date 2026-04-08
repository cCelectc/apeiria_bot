"""AIProvider model — persisted provider registry entries."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AIProvider(Model):
    """One persisted upstream provider definition."""

    __tablename__ = "ai_provider"
    __table_args__ = (UniqueConstraint("name", name="uq_ai_provider_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    provider_type: Mapped[str] = mapped_column(String(64), index=True)
    api_base: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_env_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    default_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
