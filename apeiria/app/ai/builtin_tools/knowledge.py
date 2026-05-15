"""App-owned knowledge AI tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from apeiria.ai.knowledge.service import knowledge_retrieval_service
from apeiria.ai.knowledge.settings import knowledge_settings_store
from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import (
    AIToolExecutionContext,
    AIToolLevel,
    AIToolReadiness,
    AIToolResult,
)
from apeiria.app.ai.builtin_tools.common import (
    bounded_int,
    bounded_text,
    clean_required_text,
    denied_result,
)

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeRetrievalDiagnostics,
        KnowledgeRetrievalItem,
    )

_MAX_KNOWLEDGE_RESULTS = 5
_MAX_EXCERPT_CHARS = 320


def _knowledge_readiness() -> AIToolReadiness:
    if knowledge_settings_store.get().rag_enabled:
        return AIToolReadiness.available()
    return AIToolReadiness.not_ready(
        "runtime_missing_capability",
        "knowledge retrieval is disabled",
    )


@ai_tool(
    name="knowledge.search",
    description="Search configured knowledge sources for grounded detail.",
    required_level=AIToolLevel.READ,
    readiness=_knowledge_readiness(),
)
async def search_knowledge(
    query_text: Annotated[str, "Search text for configured knowledge."],
    limit: Annotated[int | None, "Maximum results, 1-5."] = 3,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Search configured knowledge retrieval through the knowledge service."""

    del context
    query_text = clean_required_text(query_text, field="query_text")
    bounded_limit = bounded_int(
        limit,
        default=3,
        minimum=1,
        maximum=_MAX_KNOWLEDGE_RESULTS,
    )
    try:
        result = await knowledge_retrieval_service.retrieve(
            query_text=query_text,
            limit=bounded_limit,
        )
    except PermissionError as exc:
        return denied_result("knowledge.search", str(exc))

    return AIToolResult(
        summary=f"- [knowledge.search] found {len(result.items)} chunks",
        output_payload={
            "items": [_knowledge_item(item) for item in result.items[:bounded_limit]],
            "diagnostics": _knowledge_diagnostics(result.diagnostics),
        },
    )


def _knowledge_item(item: "KnowledgeRetrievalItem") -> dict[str, object]:
    return {
        "label": item.label,
        "document_id": item.document_id,
        "chunk_id": item.chunk_id,
        "title": item.title,
        "source_file_name": item.source_file_name,
        "rank": item.rank,
        "score": item.score,
        "excerpt": bounded_text(item.excerpt, max_chars=_MAX_EXCERPT_CHARS),
    }


def _knowledge_diagnostics(
    diagnostics: "KnowledgeRetrievalDiagnostics",
) -> dict[str, object]:
    return {
        "candidate_count": diagnostics.candidate_count,
        "selected_count": diagnostics.selected_count,
        "missing_embedding_count": diagnostics.missing_embedding_count,
        "stale_embedding_count": diagnostics.stale_embedding_count,
        "rerank_status": diagnostics.rerank_status,
        "degradation_reason": diagnostics.degradation_reason,
    }
