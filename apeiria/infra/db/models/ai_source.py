"""AISource model — persisted AI source entries."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AISource(Model):
    """One persisted upstream AI source definition."""

    __tablename__ = "ai_source"
    __table_args__ = (UniqueConstraint("name", name="uq_ai_source_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    capability_type: Mapped[str] = mapped_column(String(32), index=True)
    client_type: Mapped[str] = mapped_column(String(32), index=True)
    preset_type: Mapped[str] = mapped_column(String(64), index=True)
    api_base: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_env_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_headers_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    extra_config_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
