from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, TimestampMixin, _epoch_ms


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
        CheckConstraint(
            "ui_hidden_override IS NULL OR ui_hidden_override IN (0, 1)",
            name="ck_plugin_state_ui_hidden_override",
        ),
    )

    plugin_id: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    access_mode: Mapped[str] = mapped_column(
        Text, nullable=False, default="default_allow"
    )
    protection_mode: Mapped[str] = mapped_column(Text, nullable=False, default="normal")
    ui_hidden_override: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(
        Integer, nullable=False, default=_epoch_ms, onupdate=_epoch_ms
    )


class AccessRule(TimestampMixin, Base):
    __tablename__ = "access_rule"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('user', 'group')", name="ck_access_rule_subject_type"
        ),
        CheckConstraint("effect IN ('allow', 'deny')", name="ck_access_rule_effect"),
    )

    subject_type: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_id: Mapped[str] = mapped_column(Text, primary_key=True)
    plugin_id: Mapped[str] = mapped_column(Text, primary_key=True)
    effect: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class GroupState(Base):
    __tablename__ = "group_state"
    __table_args__ = (
        CheckConstraint("bot_enabled IN (0, 1)", name="ck_group_state_bot_enabled"),
    )

    group_id: Mapped[str] = mapped_column(Text, primary_key=True)
    group_name: Mapped[str | None] = mapped_column(Text)
    bot_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    disabled_plugins_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, nullable=False, default=_epoch_ms, onupdate=_epoch_ms
    )


class GroupDisabledPlugin(Base):
    __tablename__ = "group_disabled_plugin"

    group_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("group_state.group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    plugin_id: Mapped[str] = mapped_column(Text, primary_key=True)
