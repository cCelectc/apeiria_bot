"""AIEmbeddingModel model - persisted embedding model entries under one source."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class AIEmbeddingModel(Model):
    """One persisted embedding model entry owned by one AI source."""

    __tablename__ = "ai_embedding_model"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "model_identifier",
            name="uq_ai_embedding_model_source_identifier",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    model_identifier: Mapped[str] = mapped_column(String(256), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    extra_params_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
