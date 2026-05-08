"""Default knowledge-base management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException

from apeiria.ai.knowledge.chunking import KnowledgeUploadValidationError
from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .knowledge_schemas import (
    AIKnowledgeChunkItem,
    AIKnowledgeDeleteResult,
    AIKnowledgeDocumentItem,
    AIKnowledgeDocumentUploadRequest,
    AIKnowledgeRebuildDiagnosticsItem,
    AIKnowledgeRetrievalPreviewRequest,
    AIKnowledgeRetrievalResultItem,
    AIKnowledgeStateItem,
    AIKnowledgeStateUpdateRequest,
    AIKnowledgeUploadResultItem,
    to_knowledge_chunk_item,
    to_knowledge_document_item,
    to_knowledge_state_item,
    to_rebuild_diagnostics_item,
    to_retrieval_result_item,
    to_upload_result_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = getattr(session, "username", "")
    if not isinstance(username, str):
        return None
    username = username.strip()
    return username or None


@router.get("/knowledge/state", response_model=AIKnowledgeStateItem)
async def get_ai_knowledge_state(
    _: Annotated[object, Depends(require_control_panel)],
) -> AIKnowledgeStateItem:
    return to_knowledge_state_item(
        await ai_application.operations.get_knowledge_state()
    )


@router.patch("/knowledge/state", response_model=AIKnowledgeStateItem)
async def update_ai_knowledge_state(
    payload: AIKnowledgeStateUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIKnowledgeStateItem:
    return to_knowledge_state_item(
        await ai_application.operations.set_knowledge_rag_enabled(
            enabled=payload.rag_enabled,
            actor_username=_actor_username_from_claims(session),
        )
    )


@router.post("/knowledge/documents", response_model=AIKnowledgeUploadResultItem)
async def upload_ai_knowledge_document(
    payload: AIKnowledgeDocumentUploadRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIKnowledgeUploadResultItem:
    try:
        result = await ai_application.operations.upload_knowledge_document(
            source_file_name=payload.source_file_name,
            content=payload.content,
            actor_username=_actor_username_from_claims(session),
        )
    except KnowledgeUploadValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.reason) from exc
    return to_upload_result_item(result)


@router.get("/knowledge/documents", response_model=list[AIKnowledgeDocumentItem])
async def list_ai_knowledge_documents(
    _: Annotated[object, Depends(require_control_panel)],
) -> list[AIKnowledgeDocumentItem]:
    documents = await ai_application.operations.list_knowledge_documents()
    return [to_knowledge_document_item(document) for document in documents]


@router.get(
    "/knowledge/documents/{document_id}/chunks",
    response_model=list[AIKnowledgeChunkItem],
)
async def list_ai_knowledge_chunks(
    document_id: str,
    _: Annotated[object, Depends(require_control_panel)],
) -> list[AIKnowledgeChunkItem]:
    chunks = await ai_application.operations.list_knowledge_chunks(
        document_id=document_id,
    )
    return [to_knowledge_chunk_item(chunk) for chunk in chunks]


@router.post(
    "/knowledge/documents/{document_id}/rebuild",
    response_model=AIKnowledgeRebuildDiagnosticsItem,
)
async def rebuild_ai_knowledge_document_embeddings(
    document_id: str,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIKnowledgeRebuildDiagnosticsItem:
    result = await ai_application.operations.rebuild_knowledge_embeddings(
        document_id=document_id,
        actor_username=_actor_username_from_claims(session),
    )
    return to_rebuild_diagnostics_item(result)


@router.delete(
    "/knowledge/documents/{document_id}", response_model=AIKnowledgeDeleteResult
)
async def delete_ai_knowledge_document(
    document_id: str,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIKnowledgeDeleteResult:
    deleted = await ai_application.operations.delete_knowledge_document(
        document_id=document_id,
        actor_username=_actor_username_from_claims(session),
    )
    return AIKnowledgeDeleteResult(deleted=deleted)


@router.post(
    "/knowledge/retrieval/preview",
    response_model=AIKnowledgeRetrievalResultItem,
)
async def preview_ai_knowledge_retrieval(
    payload: AIKnowledgeRetrievalPreviewRequest,
    _: Annotated[object, Depends(require_control_panel)],
) -> AIKnowledgeRetrievalResultItem:
    result = await ai_application.operations.preview_knowledge_retrieval(
        query_text=payload.query_text,
        limit=payload.limit,
    )
    return to_retrieval_result_item(result)


__all__ = ["router"]
