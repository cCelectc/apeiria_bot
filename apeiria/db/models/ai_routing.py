from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, _epoch_ms

_TASK_CLASS_CHECK = (
    "task_class IN ("
    "'planner_light', 'reply_default', 'reply_roleplay', "
    "'reasoning_heavy', 'memory_extraction', 'tool_orchestration')"
)
_SCOPE_TYPE_CHECK = "scope_type IN ('global', 'group', 'user', 'conversation')"


class AIModelProfile(Base):
    __tablename__ = "ai_model_profile"

    profile_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_chat_model.model_id", ondelete="RESTRICT")
    )
    task_class: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    fallback_profile_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("ai_model_profile.profile_id", ondelete="SET NULL"),
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint(_TASK_CLASS_CHECK, name="ck_ai_model_profile_task_class"),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_model_profile_enabled"),
    )


class AIModelBinding(Base):
    __tablename__ = "ai_model_binding"

    binding_id: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text)
    scope_id: Mapped[str] = mapped_column(Text)
    profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_model_profile.profile_id", ondelete="CASCADE")
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint(_SCOPE_TYPE_CHECK, name="ck_ai_model_binding_scope_type"),
        CheckConstraint(
            "length(scope_id) > 0", name="ck_ai_model_binding_scope_id_len"
        ),
        CheckConstraint(
            "scope_type != 'global' OR scope_id = '__global__'",
            name="ck_ai_model_binding_global_sentinel",
        ),
        UniqueConstraint("scope_type", "scope_id"),
    )


class AIModelRoute(Base):
    __tablename__ = "ai_model_route"

    route_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    task_class: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    algorithm: Mapped[str] = mapped_column(Text)
    fallback_on_failure: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_ai_model_route_name_len"),
        CheckConstraint(_TASK_CLASS_CHECK, name="ck_ai_model_route_task_class"),
        CheckConstraint(
            "mode IN ('primary_fallback', 'load_balance')",
            name="ck_ai_model_route_mode",
        ),
        CheckConstraint(
            "algorithm IN ('ordered', 'weighted_random')",
            name="ck_ai_model_route_algorithm",
        ),
        CheckConstraint(
            "fallback_on_failure IN (0, 1)",
            name="ck_ai_model_route_fallback_on_failure",
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_model_route_enabled"),
        CheckConstraint(
            "mode != 'primary_fallback' OR algorithm = 'ordered'",
            name="ck_ai_model_route_mode_ordered",
        ),
        CheckConstraint(
            "mode != 'load_balance' OR algorithm = 'weighted_random'",
            name="ck_ai_model_route_mode_weighted",
        ),
        Index("idx_ai_model_route_task_class", "task_class", "enabled"),
    )


class AIModelRouteMember(Base):
    __tablename__ = "ai_model_route_member"

    route_member_id: Mapped[str] = mapped_column(Text, primary_key=True)
    route_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_model_route.route_id", ondelete="CASCADE")
    )
    profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_model_profile.profile_id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_ai_model_route_member_position"),
        CheckConstraint("weight > 0", name="ck_ai_model_route_member_weight"),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_model_route_member_enabled"),
        UniqueConstraint("route_id", "profile_id"),
        UniqueConstraint("route_id", "position"),
        Index("idx_ai_model_route_member_route", "route_id", "enabled", "position"),
    )


class AIModelRouteBinding(Base):
    __tablename__ = "ai_model_route_binding"

    binding_id: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text)
    scope_id: Mapped[str] = mapped_column(Text)
    task_class: Mapped[str] = mapped_column(Text)
    route_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_model_route.route_id", ondelete="CASCADE")
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint(_SCOPE_TYPE_CHECK, name="ck_ai_model_route_binding_scope_type"),
        CheckConstraint(
            "length(scope_id) > 0", name="ck_ai_model_route_binding_scope_id_len"
        ),
        CheckConstraint(_TASK_CLASS_CHECK, name="ck_ai_model_route_binding_task_class"),
        CheckConstraint(
            "scope_type != 'global' OR scope_id = '__global__'",
            name="ck_ai_model_route_binding_global_sentinel",
        ),
        UniqueConstraint("scope_type", "scope_id", "task_class"),
        Index("idx_ai_model_route_binding_route", "route_id"),
    )
