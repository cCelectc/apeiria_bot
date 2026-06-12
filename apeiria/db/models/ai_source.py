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
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from apeiria.db.base import Base, _epoch_ms


class AISource(Base):
    __tablename__ = "ai_source"

    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    capability_type: Mapped[str] = mapped_column(Text)
    client_type: Mapped[str] = mapped_column(Text)
    adapter_kind: Mapped[str] = mapped_column(Text, default="openai_compatible")
    preset_type: Mapped[str] = mapped_column(Text)
    api_base: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    custom_headers_json: Mapped[str] = mapped_column(Text, default="{}")
    extra_config_json: Mapped[str] = mapped_column(Text, default="{}")
    capability_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    default_options_json: Mapped[str] = mapped_column(Text, default="{}")
    capability_provenance_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[int] = mapped_column(
        Integer, default=_epoch_ms, onupdate=_epoch_ms
    )

    __table_args__ = (
        CheckConstraint(
            "capability_type IN ("
            "'chat_completion', 'embedding', 'speech_to_text', "
            "'text_to_speech', 'rerank')",
            name="ck_ai_source_capability_type",
        ),
        CheckConstraint(
            "client_type IN ("
            "'openai', 'anthropic', 'generic_rerank', 'gemini', 'ollama')",
            name="ck_ai_source_client_type",
        ),
        CheckConstraint(
            "adapter_kind IN ("
            "'openai_compatible', 'anthropic_compatible', 'generic_rerank', "
            "'gemini_native', 'ollama_native')",
            name="ck_ai_source_adapter_kind",
        ),
        CheckConstraint(
            "preset_type IN ("
            "'openai_compatible', 'openai_compatible_embedding', "
            "'openai_compatible_stt', 'openai_compatible_tts', "
            "'generic_rerank_api', 'anthropic_compatible', "
            "'gemini_native', 'gemini_native_embedding', "
            "'ollama_native', 'ollama_native_embedding')",
            name="ck_ai_source_preset_type",
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_ai_source_enabled"),
        CheckConstraint(
            "timeout_seconds IS NULL OR timeout_seconds > 0",
            name="ck_ai_source_timeout_seconds",
        ),
        CheckConstraint(
            "json_valid(custom_headers_json)",
            name="ck_ai_source_custom_headers_json",
        ),
        CheckConstraint(
            "json_valid(extra_config_json)",
            name="ck_ai_source_extra_config_json",
        ),
        CheckConstraint(
            "json_valid(capability_metadata_json)",
            name="ck_ai_source_capability_metadata_json",
        ),
        CheckConstraint(
            "json_valid(default_options_json)",
            name="ck_ai_source_default_options_json",
        ),
        CheckConstraint(
            "json_valid(capability_provenance_json)",
            name="ck_ai_source_capability_provenance_json",
        ),
    )


class _SourceModelMixin:
    @declared_attr
    def model_id(self) -> Mapped[str]:
        return mapped_column(Text, primary_key=True)

    @declared_attr
    def source_id(self) -> Mapped[str]:
        return mapped_column(
            Text,
            ForeignKey("ai_source.source_id", ondelete="RESTRICT"),
        )

    @declared_attr
    def model_identifier(self) -> Mapped[str]:
        return mapped_column(Text)

    @declared_attr
    def display_name(self) -> Mapped[str]:
        return mapped_column(Text)

    @declared_attr
    def enabled(self) -> Mapped[int]:
        return mapped_column(Integer, default=1)

    @declared_attr
    def is_default(self) -> Mapped[int]:
        return mapped_column(Integer, default=0)

    @declared_attr
    def extra_params_json(self) -> Mapped[str]:
        return mapped_column(Text, default="{}")

    @declared_attr
    def capability_metadata_json(self) -> Mapped[str]:
        return mapped_column(Text, default="{}")

    @declared_attr
    def default_options_json(self) -> Mapped[str]:
        return mapped_column(Text, default="{}")

    @declared_attr
    def capability_provenance_json(self) -> Mapped[str]:
        return mapped_column(Text, default="{}")

    @declared_attr
    def updated_at(self) -> Mapped[int]:
        return mapped_column(Integer, default=_epoch_ms, onupdate=_epoch_ms)

    @declared_attr
    def __table_args__(self) -> tuple:  # type: ignore[override]
        table = self.__tablename__
        return (
            UniqueConstraint("source_id", "model_identifier"),
            CheckConstraint("enabled IN (0, 1)", name=f"ck_{table}_enabled"),
            CheckConstraint("is_default IN (0, 1)", name=f"ck_{table}_is_default"),
            CheckConstraint(
                "json_valid(extra_params_json)",
                name=f"ck_{table}_extra_params_json",
            ),
            CheckConstraint(
                "json_valid(capability_metadata_json)",
                name=f"ck_{table}_capability_metadata_json",
            ),
            CheckConstraint(
                "json_valid(default_options_json)",
                name=f"ck_{table}_default_options_json",
            ),
            CheckConstraint(
                "json_valid(capability_provenance_json)",
                name=f"ck_{table}_capability_provenance_json",
            ),
            Index(f"idx_{table}_source_id", "source_id"),
            Index(
                f"idx_{table}_one_default_per_source",
                "source_id",
                unique=True,
                sqlite_where=text("is_default = 1"),
            ),
        )


class AIChatModel(_SourceModelMixin, Base):
    __tablename__ = "ai_chat_model"


class AIEmbeddingModel(_SourceModelMixin, Base):
    __tablename__ = "ai_embedding_model"


class AISTTModel(_SourceModelMixin, Base):
    __tablename__ = "ai_stt_model"


class AITTSModel(_SourceModelMixin, Base):
    __tablename__ = "ai_tts_model"


class AIRerankModel(_SourceModelMixin, Base):
    __tablename__ = "ai_rerank_model"
