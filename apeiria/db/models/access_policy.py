"""AccessPolicyEntry model — explicit per-plugin allow/deny rules."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AccessPolicyEntry(Model):
    """One explicit access rule for a user or group on one plugin."""

    __tablename__ = "access_policy_entry"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "plugin_module",
            name="uq_access_policy_subject_plugin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(16), index=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    plugin_module: Mapped[str] = mapped_column(String(256), index=True)
    effect: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
