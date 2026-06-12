from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, TimestampMixin


class WebUIAuthSecret(TimestampMixin, Base):
    __tablename__ = "webui_auth_secret"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_webui_auth_secret_singleton"),
        CheckConstraint(
            "length(token_secret) > 0", name="ck_webui_auth_secret_nonempty"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_secret: Mapped[str] = mapped_column(Text, nullable=False)


class WebUIAccount(TimestampMixin, Base):
    __tablename__ = "webui_account"
    __table_args__ = (
        CheckConstraint("length(username) > 0", name="ck_webui_account_username"),
        CheckConstraint(
            "length(password_hash) > 0", name="ck_webui_account_password_hash"
        ),
        CheckConstraint("is_disabled IN (0, 1)", name="ck_webui_account_is_disabled"),
        CheckConstraint(
            "session_version >= 0", name="ck_webui_account_session_version"
        ),
        Index("idx_webui_account_username", "username"),
    )

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_disabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login_at: Mapped[int | None] = mapped_column(Integer)
    password_changed_at: Mapped[int | None] = mapped_column(Integer)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
