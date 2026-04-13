"""AIMemoryEmbedding model — stored embedding vectors for knowledge memories."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from nonebot_plugin_orm import Model
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AIMemoryEmbedding(Model):
    """Embedding payload for one memory item."""

    __tablename__ = "ai_memory_embedding"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ai_memory_item.memory_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    embedding_model: Mapped[str] = mapped_column(String(64), default="local_bigrams_v1")
    vector_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        onupdate=func.now(),
    )
