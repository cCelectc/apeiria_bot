from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, ISOTimestampMixin, _now_iso


class AccessRule(ISOTimestampMixin, Base):
    __tablename__ = "access_rules"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('user', 'group')",
            name="ck_access_rules_subject_type",
        ),
        CheckConstraint(
            "effect IN ('allow', 'deny')",
            name="ck_access_rules_effect",
        ),
    )

    subject_type: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_id: Mapped[str] = mapped_column(Text, primary_key=True)
    plugin_name: Mapped[str] = mapped_column(Text, primary_key=True)
    effect: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class PluginState(Base):
    __tablename__ = "plugin_state"
    __table_args__ = (
        CheckConstraint("enabled IN (0, 1)", name="ck_plugin_state_enabled"),
        CheckConstraint(
            "access_mode IN ('default_allow', 'default_deny')",
            name="ck_plugin_state_access_mode",
        ),
        CheckConstraint(
            "protection_mode IN ('normal', 'required')",
            name="ck_plugin_state_protection_mode",
        ),
    )

    plugin_id: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    access_mode: Mapped[str] = mapped_column(Text, default="default_allow")
    protection_mode: Mapped[str] = mapped_column(Text, default="normal")
    updated_at: Mapped[str] = mapped_column(Text, default=_now_iso, onupdate=_now_iso)


class GroupState(Base):
    __tablename__ = "group_state"
    __table_args__ = (
        CheckConstraint("bot_enabled IN (0, 1)", name="ck_group_state_bot_enabled"),
    )

    group_id: Mapped[str] = mapped_column(Text, primary_key=True)
    group_name: Mapped[str | None] = mapped_column(Text)
    bot_enabled: Mapped[int] = mapped_column(Integer, default=1)
    disabled_plugins_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[str] = mapped_column(Text, default=_now_iso, onupdate=_now_iso)


class GroupDisabledPlugin(Base):
    __tablename__ = "group_disabled_plugin"

    group_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("group_state.group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    plugin_id: Mapped[str] = mapped_column(Text, primary_key=True)
