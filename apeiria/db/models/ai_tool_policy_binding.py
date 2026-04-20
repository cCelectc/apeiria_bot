"""AIToolPolicyBinding model — persisted tool policy bindings by scope."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import Boolean, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AIToolPolicyBinding(Model):
    """One persisted tool policy binding."""

    __tablename__ = "ai_tool_policy_binding"
    __table_args__ = (
        UniqueConstraint(
            "scope_type",
            "scope_id",
            name="uq_ai_tool_policy_binding_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    binding_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_id: Mapped[str] = mapped_column(String(128), index=True)
    allow_read_only_tools: Mapped[bool] = mapped_column(Boolean, default=True)
    capability_mode: Mapped[str] = mapped_column(String(32), default="off")
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
