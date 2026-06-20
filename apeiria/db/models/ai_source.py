from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, ISOTimestampMixin


class AISource(ISOTimestampMixin, Base):
    __tablename__ = "ai_sources"
    __table_args__ = (
        CheckConstraint(
            "adapter IN ('openai_compatible', 'anthropic_compatible', "
            "'gemini_native', 'fastembed', 'generic_rerank')",
            name="ck_ai_sources_adapter",
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_sources_enabled"),
        CheckConstraint(
            "timeout_seconds IS NULL OR timeout_seconds > 0",
            name="ck_ai_sources_timeout_seconds",
        ),
    )

    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    adapter: Mapped[str] = mapped_column(Text)
    api_base: Mapped[str | None] = mapped_column(Text)
    api_key_env: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    extra_config_json: Mapped[str] = mapped_column(Text, default="{}")


class AIChatModel(ISOTimestampMixin, Base):
    __tablename__ = "ai_chat_models"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "model_identifier", name="uq_ai_chat_models_source_model"
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_chat_models_enabled"),
        CheckConstraint("is_default IN (0, 1)", name="ck_ai_chat_models_is_default"),
        CheckConstraint(
            "supports_reasoning IN (0, 1)",
            name="ck_ai_chat_models_supports_reasoning",
        ),
        Index(
            "ix_ai_chat_models_one_default",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )

    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_sources.source_id", ondelete="RESTRICT")
    )
    model_identifier: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    context_window: Mapped[int] = mapped_column(Integer, default=128000)
    supports_reasoning: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[int] = mapped_column(Integer, default=0)
    extra_params_json: Mapped[str] = mapped_column(Text, default="{}")


class AIEmbeddingModel(ISOTimestampMixin, Base):
    __tablename__ = "ai_embedding_models"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "model_identifier",
            name="uq_ai_embedding_models_source_model",
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_embedding_models_enabled"),
        CheckConstraint(
            "is_default IN (0, 1)", name="ck_ai_embedding_models_is_default"
        ),
        Index(
            "ix_ai_embedding_models_one_default",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )

    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_sources.source_id", ondelete="RESTRICT")
    )
    model_identifier: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    dimensions: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[int] = mapped_column(Integer, default=0)
    extra_params_json: Mapped[str] = mapped_column(Text, default="{}")


class AIRerankModel(ISOTimestampMixin, Base):
    __tablename__ = "ai_rerank_models"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "model_identifier", name="uq_ai_rerank_models_source_model"
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_rerank_models_enabled"),
        CheckConstraint("is_default IN (0, 1)", name="ck_ai_rerank_models_is_default"),
        Index(
            "ix_ai_rerank_models_one_default",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )

    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_sources.source_id", ondelete="RESTRICT")
    )
    model_identifier: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[int] = mapped_column(Integer, default=0)
    extra_params_json: Mapped[str] = mapped_column(Text, default="{}")
