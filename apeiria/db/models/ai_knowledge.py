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

from apeiria.db.base import Base, ISOTimestampMixin, _now_iso


class KnowledgeDocument(ISOTimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'embedded', 'degraded', 'failed')",
            name="ck_knowledge_documents_status",
        ),
        CheckConstraint(
            "chunk_count >= 0",
            name="ck_knowledge_documents_chunk_count",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text)
    source_file_name: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_knowledge_chunks_chunk_index",
        ),
        CheckConstraint(
            "embedding_status IN ('pending', 'embedded', 'failed')",
            name="ck_knowledge_chunks_embedding_status",
        ),
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_knowledge_chunks_doc_index"
        ),
        Index("idx_knowledge_chunks_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_status: Mapped[str] = mapped_column(Text, default="pending")
    created_at: Mapped[str] = mapped_column(Text, default=_now_iso)
