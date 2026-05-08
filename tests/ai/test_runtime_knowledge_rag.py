from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.ai.knowledge.models import (
    KnowledgeRetrievalDiagnostics,
    KnowledgeRetrievalItem,
    KnowledgeRetrievalResult,
)
from apeiria.ai.prompting import ReplyPromptInput, build_reply_final_packet
from apeiria.app.ai.runtime.context.projection import project_runtime_context
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.session.context import RuntimeContextMaterials
from apeiria.conversation.models import ChatContextMessageView, ChatSessionIdentity

EXPECTED_RAG_CANDIDATE_COUNT = 3

if TYPE_CHECKING:
    from pytest import MonkeyPatch


@dataclass(frozen=True)
class _Persona:
    persona_id: str = "persona-1"
    system_prompt: str = "You are Apeiria."
    style_prompt: str = "Reply plainly."


def _rag_item() -> KnowledgeRetrievalItem:
    return KnowledgeRetrievalItem(
        label="K1",
        document_id="kdoc_1",
        chunk_id="kchunk_1",
        title="Manual",
        source_file_name="manual.md",
        rank=1,
        score=0.87,
        rerank_score=None,
        excerpt="Apeiria RAG stores deterministic chunks.",
    )


def _turn_input():
    from apeiria.app.ai.runtime.session.context import (
        RuntimeTurnInput,
        RuntimeTurnSource,
    )

    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    return RuntimeTurnInput(
        identity=identity,
        sender_id="bot-1",
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="How does RAG work?",
            source_message_id="msg-1",
            user_id="user-1",
            is_private=True,
        ),
    )


def _context() -> RuntimeContextMaterials:
    now = datetime.now(timezone.utc)
    return RuntimeContextMaterials(
        turns=[
            ChatContextMessageView(
                message_id="msg-1",
                author_role="user",
                author_id="user-1",
                author_name="User",
                text_content="How does RAG work?",
                content=None,
                created_at=now,
            )
        ],
        conversation_summary=None,
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=object(),  # type: ignore[arg-type]
        tool_policy=object(),  # type: ignore[arg-type]
        persona=_Persona(),
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )


def test_reply_prompt_renders_distinct_rag_section() -> None:
    packet = build_reply_final_packet(
        ReplyPromptInput(
            persona=_Persona(),
            scene_type="private",
            relationship=None,
            tool_policy=None,
            tool_results=(),
            memories=(),
            rag_chunks=(_rag_item(),),
            turns=(),
            person_profile=(),
        )
    )

    rag_section = next(
        section for section in packet.sections if section.name == "RAGKnowledge"
    )
    assert "[K1] Manual (manual.md)" in rag_section.content
    assert "Apeiria RAG stores deterministic chunks." in rag_section.content


def test_runtime_projection_carries_rag_chunks_and_diagnostics() -> None:
    context = replace(
        _context(),
        rag_chunks=(_rag_item(),),
        rag_diagnostics=KnowledgeRetrievalDiagnostics(
            candidate_count=3,
            selected_count=1,
            rerank_status="not_configured",
        ),
    )

    projection = project_runtime_context(
        turn=_turn_input(),
        context=context,
        social_decision=None,
        skill_runtime=RuntimeToolLoopResult(policy_text="", result_lines=(), turns=()),
    )

    assert projection.prompt.rag_chunks == (_rag_item(),)
    assert projection.preview.rag_chunks == (_rag_item(),)
    assert projection.diagnostics.rag_enabled is True
    assert projection.diagnostics.rag_selected_count == 1
    assert (
        projection.diagnostics.as_dict()["rag_candidate_count"]
        == EXPECTED_RAG_CANDIDATE_COUNT
    )


def test_context_rag_collection_is_disabled_by_default(
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.app.ai.runtime.context import materials as materials_module

    called = False

    async def retrieve(**_: object) -> KnowledgeRetrievalResult:
        nonlocal called
        called = True
        return KnowledgeRetrievalResult(
            items=(), diagnostics=KnowledgeRetrievalDiagnostics()
        )

    monkeypatch.setattr(
        materials_module.knowledge_retrieval_service,
        "retrieve",
        retrieve,
    )

    def disabled_settings() -> object:
        return type("Settings", (), {"rag_enabled": False})()

    monkeypatch.setattr(
        materials_module.knowledge_settings_store, "get", disabled_settings
    )

    async def scenario() -> None:
        result = await materials_module.retrieve_rag_for_context(
            query_text="hello",
            limit=3,
        )

        assert result.items == ()
        assert result.diagnostics.degradation_reason == "disabled"
        assert called is False

    asyncio.run(scenario())


def test_context_rag_collection_is_read_only_when_enabled(
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.app.ai.runtime.context import materials as materials_module

    async def retrieve(**kwargs: object) -> KnowledgeRetrievalResult:
        assert kwargs["mutate_embeddings"] is False
        return KnowledgeRetrievalResult(
            items=(_rag_item(),),
            diagnostics=KnowledgeRetrievalDiagnostics(
                candidate_count=2,
                selected_count=1,
                rerank_status="not_configured",
            ),
        )

    monkeypatch.setattr(
        materials_module.knowledge_retrieval_service,
        "retrieve",
        retrieve,
    )

    def enabled_settings() -> object:
        return type("Settings", (), {"rag_enabled": True})()

    monkeypatch.setattr(
        materials_module.knowledge_settings_store, "get", enabled_settings
    )

    async def scenario() -> None:
        result = await materials_module.retrieve_rag_for_context(
            query_text="hello",
            limit=3,
        )

        assert result.items == (_rag_item(),)
        assert result.diagnostics.selected_count == 1

    asyncio.run(scenario())
