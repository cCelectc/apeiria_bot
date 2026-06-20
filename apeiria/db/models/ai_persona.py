from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, ISOTimestampMixin, _now_iso


class Persona(ISOTimestampMixin, Base):
    __tablename__ = "personas"
    __table_args__ = (
        CheckConstraint("enabled IN (0, 1)", name="ck_personas_enabled"),
        CheckConstraint("is_default IN (0, 1)", name="ck_personas_is_default"),
        Index(
            "ix_personas_one_default",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[int] = mapped_column(Integer, default=0)


class PersonaBinding(Base):
    __tablename__ = "persona_bindings"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    persona_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("personas.id", ondelete="CASCADE")
    )
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
