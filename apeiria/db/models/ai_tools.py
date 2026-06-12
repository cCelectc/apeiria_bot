from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _epoch_ms


class AIToolPolicy(Base):
    __tablename__ = "ai_tool_policy"

    binding_id: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text)
    scope_id: Mapped[str] = mapped_column(Text)
    allowed_level: Mapped[str] = mapped_column(Text, default="none")
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('global', 'group', 'user', 'conversation')",
            name="ck_ai_tool_policy_scope_type",
        ),
        CheckConstraint(
            "allowed_level IN ('none', 'read', 'write', 'host', 'admin')",
            name="ck_ai_tool_policy_allowed_level",
        ),
        CheckConstraint("length(scope_id) > 0", name="ck_ai_tool_policy_scope_id_len"),
        CheckConstraint(
            "scope_type != 'global' OR scope_id = '__global__'",
            name="ck_ai_tool_policy_global_scope",
        ),
        UniqueConstraint("scope_type", "scope_id", name="uq_ai_tool_policy_scope"),
    )
