from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
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


class RefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        CheckConstraint(
            "revoked IN (0, 1)",
            name="ck_auth_refresh_tokens_revoked",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webui_accounts.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[str] = mapped_column(Text)
    revoked: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)


class WebUIAuthSecret(Base):
    __tablename__ = "webui_auth_secret"
    __table_args__ = (CheckConstraint("id = 1", name="ck_webui_auth_secret_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_secret: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
