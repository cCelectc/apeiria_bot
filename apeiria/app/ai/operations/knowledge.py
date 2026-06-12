"""Knowledge-base admin operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.knowledge.repository import KnowledgeRepository
from apeiria.ai.knowledge.settings import knowledge_settings_store
from apeiria.app.ai.diagnostics.audit import record_ai_admin_audit
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeChunkDefinition,
        KnowledgeDocumentDefinition,
        KnowledgeRebuildDiagnostics,
        KnowledgeRetrievalResult,
        KnowledgeUploadResult,
    )


@dataclass(frozen=True)
class KnowledgeState:
    """Management state for the default knowledge base."""

    rag_enabled: bool
    document_count: int
    chunk_count: int


class KnowledgeAdminMixin:
    """Admin workflows for the default knowledge base."""

    async def get_knowledge_state(self) -> KnowledgeState:
        repository = KnowledgeRepository()
        documents = repository.list_documents()
        chunks = repository.list_chunks()
        settings = knowledge_settings_store.get()
        return KnowledgeState(
            rag_enabled=settings.rag_enabled,
            document_count=len(documents),
            chunk_count=len(chunks),
        )

    async def set_knowledge_rag_enabled(
        self,
        *,
        enabled: bool,
        actor_username: str | None = None,
    ) -> KnowledgeState:
        knowledge_settings_store.set_rag_enabled(enabled=enabled)
        record_ai_admin_audit(
            "ai_knowledge_rag_enabled_updated",
            actor_username=actor_username,
            detail=f"enabled={enabled}",
        )
        return await self.get_knowledge_state()

    async def upload_knowledge_document(
        self,
        *,
        source_file_name: str,
        content: str | bytes,
        actor_username: str | None = None,
    ) -> KnowledgeUploadResult:
        result = await ai_wiring.knowledge_service.upload_document(
            source_file_name=source_file_name,
            content=content,
        )
        record_ai_admin_audit(
            "ai_knowledge_document_uploaded",
            actor_username=actor_username,
            detail=result.document.document_id,
        )
        return result

    async def list_knowledge_documents(self) -> list[KnowledgeDocumentDefinition]:
        return KnowledgeRepository().list_documents()

    async def get_knowledge_document(
        self,
        *,
        document_id: str,
    ) -> KnowledgeDocumentDefinition | None:
        return KnowledgeRepository().get_document(document_id=document_id)

    async def list_knowledge_chunks(
        self,
        *,
        document_id: str | None = None,
    ) -> list[KnowledgeChunkDefinition]:
        return KnowledgeRepository().list_chunks(document_id=document_id)

    async def rebuild_knowledge_embeddings(
        self,
        *,
        document_id: str | None = None,
        actor_username: str | None = None,
    ) -> KnowledgeRebuildDiagnostics:
        result = await ai_wiring.knowledge_service.rebuild_embeddings(
            document_id=document_id,
        )
        record_ai_admin_audit(
            "ai_knowledge_embeddings_rebuilt",
            actor_username=actor_username,
            detail=document_id or "default",
        )
        return result

    async def preview_knowledge_retrieval(
        self,
        *,
        query_text: str,
        limit: int,
    ) -> KnowledgeRetrievalResult:
        return await ai_wiring.knowledge_service.retrieve(
            query_text=query_text,
            limit=limit,
        )

    async def delete_knowledge_document(
        self,
        *,
        document_id: str,
        actor_username: str | None = None,
    ) -> bool:
        deleted = await ai_wiring.knowledge_service.delete_document(
            document_id=document_id
        )
        if deleted:
            record_ai_admin_audit(
                "ai_knowledge_document_deleted",
                actor_username=actor_username,
                detail=document_id,
            )
        return deleted
