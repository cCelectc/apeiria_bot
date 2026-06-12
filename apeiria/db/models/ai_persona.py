from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, TimestampMixin


class AIPersona(TimestampMixin, Base):
    __tablename__ = "ai_persona"

    persona_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text)
    style_prompt: Mapped[str] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_persona_enabled"),
    )


class AIPersonaBinding(TimestampMixin, Base):
    __tablename__ = "ai_persona_binding"

    binding_id: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text)
    scope_id: Mapped[str] = mapped_column(Text)
    persona_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_persona.persona_id", ondelete="CASCADE")
    )

    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('global', 'group', 'user', 'conversation')",
            name="ck_ai_persona_binding_scope_type",
        ),
        CheckConstraint(
            "length(scope_id) > 0", name="ck_ai_persona_binding_scope_id_len"
        ),
        CheckConstraint(
            "scope_type != 'global' OR scope_id = '__global__'",
            name="ck_ai_persona_binding_global_sentinel",
        ),
        UniqueConstraint("scope_type", "scope_id"),
    )
