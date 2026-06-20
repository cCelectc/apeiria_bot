from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, ISOTimestampMixin, _now_iso


class WebUIAccount(ISOTimestampMixin, Base):
    __tablename__ = "webui_accounts"
    __table_args__ = (
        CheckConstraint(
            "must_change_password IN (0, 1)",
            name="ck_webui_accounts_must_change_password",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    password_changed_at: Mapped[str | None] = mapped_column(Text)
    must_change_password: Mapped[int] = mapped_column(Integer, default=1)


class WebUIAuthSecret(Base):
    __tablename__ = "webui_auth_secret"
    __table_args__ = (CheckConstraint("id = 1", name="ck_webui_auth_secret_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_secret: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
