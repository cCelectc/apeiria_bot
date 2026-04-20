"""PluginPolicyEntry model — framework-owned plugin governance settings."""

from __future__ import annotations

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class PluginPolicyEntry(Model):
    """One governance policy record for one plugin module."""

    __tablename__ = "plugin_policy_entry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plugin_module: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    access_mode: Mapped[str] = mapped_column(String(16), default="default_allow")
    required_level: Mapped[int] = mapped_column(default=0)
    protection_mode: Mapped[str] = mapped_column(String(16), default="normal")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
