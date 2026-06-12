from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, TimestampMixin


class ApeiriaSchemaMetaModel(TimestampMixin, Base):
    __tablename__ = "apeiria_schema_meta"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_apeiria_schema_meta_singleton"),
        CheckConstraint("length(schema_line) > 0", name="ck_schema_line_nonempty"),
        CheckConstraint("schema_version > 0", name="ck_schema_version_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_line: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
