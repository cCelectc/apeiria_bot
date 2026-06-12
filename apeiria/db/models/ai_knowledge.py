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

from apeiria.db.base import Base, TimestampMixin


class AIKnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "ai_knowledge_document"

    document_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_file_name: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'embedded', 'degraded', 'failed')",
            name="ck_ai_knowledge_document_status",
        ),
        CheckConstraint(
            "chunk_count >= 0",
            name="ck_ai_knowledge_document_chunk_count",
        ),
        Index("ix_ai_knowledge_document_updated_at", "updated_at"),
    )


class AIKnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "ai_knowledge_chunk"

    chunk_id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_knowledge_document.document_id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    chunk_hash: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_status: Mapped[str] = mapped_column(Text, default="missing")

    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_ai_knowledge_chunk_ordinal"),
        CheckConstraint("char_count >= 0", name="ck_ai_knowledge_chunk_char_count"),
        CheckConstraint(
            "embedding_status IN ('missing', 'embedded', 'stale', 'failed')",
            name="ck_ai_knowledge_chunk_embedding_status",
        ),
        UniqueConstraint(
            "document_id",
            "ordinal",
            name="uq_ai_knowledge_chunk_doc_ordinal",
        ),
        Index("ix_ai_knowledge_chunk_document", "document_id", "ordinal"),
        Index("ix_ai_knowledge_chunk_embedding_status", "embedding_status"),
    )
