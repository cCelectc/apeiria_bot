"""PluginInfo model — plugin registry, synced on startup."""

from __future__ import annotations

from nonebot_plugin_orm import Model
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class PluginInfo(Model):
    """Plugin registry — synced from loaded plugins on startup."""

    __tablename__ = "plugin_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_name: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage: Mapped[str | None] = mapped_column(Text, nullable=True)
    plugin_type: Mapped[str] = mapped_column(String(32), default="normal")
    is_ui_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_level: Mapped[int] = mapped_column(default=0)
    is_global_enabled: Mapped[bool] = mapped_column(default=True)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
