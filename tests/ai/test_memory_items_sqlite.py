from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

OLD_MEMORY_DAYS = 5
RETENTION_DAYS = 1


def test_memory_items_use_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory.models import AIMemoryQuery
    from apeiria.ai.memory.service import AIMemoryCreateInput
    from apeiria.app.ai.wiring import ai_wiring
    from tests.db_helpers import async_db

    async def scenario() -> None:
        async with async_db(database_runtime.database_path(), create_tables=False):
            created = await ai_wiring.memory_service.create_memory(
                AIMemoryCreateInput(
                    anchor_type="user",
                    anchor_id="user-1",
                    memory_layer="long_term",
                    memory_kind="preference",
                    content="likes short answers",
                    salience=0.7,
                    confidence=0.8,
                ),
            )

            duplicate = await ai_wiring.memory_service.create_memory_if_absent(
                AIMemoryCreateInput(
                    anchor_type="user",
                    anchor_id="user-1",
                    memory_layer="long_term",
                    memory_kind="preference",
                    content="likes short answers",
                ),
            )
            assert duplicate is None

            recalled = await ai_wiring.memory_service.recall_memories(
                AIMemoryQuery(
                    anchor_type="user",
                    anchor_id="user-1",
                    query_text="short",
                    limit=10,
                    memory_layer="long_term",
                ),
            )
            assert [item.memory_id for item in recalled] == [created.memory_id]
            assert recalled[0].last_recalled_at is not None

            suppressed = await ai_wiring.memory_service.set_memory_state(
                memory_id=created.memory_id,
                lifecycle_state="suppressed",
                governance_reason="test suppression",
            )
            assert suppressed is not None
            assert suppressed.lifecycle_state == "suppressed"

            assert (
                await ai_wiring.memory_service.retrieve_memories(
                    AIMemoryQuery(
                        anchor_type="user",
                        anchor_id="user-1",
                        query_text="short",
                        limit=10,
                        memory_layer="long_term",
                    ),
                )
                == []
            )

            listed = await ai_wiring.memory_service.list_memories(
                anchor_type="user",
                anchor_id="user-1",
                lifecycle_states=(),
            )
            assert [item.memory_id for item in listed] == [created.memory_id]

            deleted = await ai_wiring.memory_service.delete_memory(
                memory_id=created.memory_id,
            )
            assert deleted is True
            assert (
                await ai_wiring.memory_service.get_memory(memory_id=created.memory_id)
                is None
            )

    asyncio.run(scenario())


def test_memory_lifecycle_changes_sync_sparse_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory.service import (
        AIMemoryCreateInput,
        _memory_to_retrieval_document,
    )
    from apeiria.ai.retrieval.sparse import retrieval_sparse_index
    from apeiria.app.ai.wiring import ai_wiring
    from tests.db_helpers import async_db

    async def select_default_model(*, capability_type: str) -> object | None:
        del capability_type
        return None

    monkeypatch.setattr(
        ai_wiring.retrieval_service._capability_selection_service,
        "select_default_model",
        select_default_model,
    )

    async def scenario() -> None:
        async with async_db(database_runtime.database_path(), create_tables=False):
            memory = await ai_wiring.memory_service.create_memory(
                AIMemoryCreateInput(
                    anchor_type="user",
                    anchor_id="user-1",
                    memory_layer="long_term",
                    memory_kind="note",
                    content="prefers retrieval architecture notes",
                )
            )

            await ai_wiring.memory_service.set_memory_state(
                memory_id=memory.memory_id,
                lifecycle_state="suppressed",
                default_use_mode="ignore",
                governance_reason="test suppression",
            )

            suppressed_document = _memory_to_retrieval_document(memory)
            suppressed_result = await retrieval_sparse_index.search(
                query_text="retrieval architecture",
                documents=(suppressed_document,),
                limit=1,
            )

            assert suppressed_result.candidates == ()

            await ai_wiring.memory_service.set_memory_state(
                memory_id=memory.memory_id,
                lifecycle_state="active",
                default_use_mode="context",
                governance_reason="test reactivation",
            )
            reactivated = await ai_wiring.memory_service.get_memory(
                memory_id=memory.memory_id
            )
            assert reactivated is not None

            reactivated_document = _memory_to_retrieval_document(reactivated)
            reactivated_result = await retrieval_sparse_index.search(
                query_text="retrieval architecture",
                documents=(reactivated_document,),
                limit=1,
            )

            assert [
                candidate.document.document_id
                for candidate in reactivated_result.candidates
            ] == [reactivated_document.document_id]

    asyncio.run(scenario())


def test_consolidate_anchor_summary_creates_first_summary_memory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory.service import AIMemoryCreateInput
    from apeiria.app.ai.wiring import ai_wiring
    from tests.db_helpers import async_db

    async def scenario() -> None:
        async with async_db(database_runtime.database_path(), create_tables=False):
            for content in ("likes concise answers", "works on Apeiria"):
                await ai_wiring.memory_service.create_memory(
                    AIMemoryCreateInput(
                        anchor_type="user",
                        anchor_id="user-1",
                        memory_layer="long_term",
                        memory_kind="note",
                        content=content,
                    ),
                )

            await ai_wiring.memory_service.consolidate_anchor_summary(
                anchor_type="user",
                anchor_id="user-1",
            )

            summaries = await ai_wiring.memory_service.list_memories(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="summary",
            )

            assert len(summaries) == 1
            assert summaries[0].is_editable is False
            assert "likes concise answers" in summaries[0].content

    asyncio.run(scenario())


def test_suppressed_memory_retention_deletes_sqlite_rows_and_embedding(
    tmp_path: Path,
) -> None:
    from apeiria.ai.memory.embedding_store import ai_memory_embedding_store
    from apeiria.ai.retention import AIRetentionService
    from apeiria.db.engine import get_session
    from apeiria.db.models.ai_memory import AIMemoryItem
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    old_epoch_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=OLD_MEMORY_DAYS)).timestamp()
        * 1000
    )
    new_epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    async def run() -> None:
        async with async_db(db_path):
            async with get_session() as session:
                for memory_id, lifecycle_state, created_at in (
                    ("mem_old", "suppressed", old_epoch_ms),
                    ("mem_new", "suppressed", new_epoch_ms),
                    ("mem_visible", "active", old_epoch_ms),
                ):
                    session.add(
                        AIMemoryItem(
                            memory_id=memory_id,
                            anchor_type="user",
                            anchor_id="user-1",
                            memory_layer="knowledge",
                            memory_kind="note",
                            content=memory_id,
                            is_editable=1,
                            lifecycle_state=lifecycle_state,
                            default_use_mode=(
                                "ignore"
                                if lifecycle_state == "suppressed"
                                else "context"
                            ),
                            salience=0.5,
                            confidence=0.5,
                            created_at=created_at,
                        )
                    )
                await session.commit()

            ai_memory_embedding_store.upsert(
                memory_id="mem_old",
                embedding_model="local",
                vector=[1.0],
            )

            deleted = await AIRetentionService().cleanup_suppressed_memories(
                retention_days=RETENTION_DAYS
            )

            from sqlalchemy import select

            async with get_session() as session:
                rows = (
                    (
                        await session.execute(
                            select(AIMemoryItem.memory_id).order_by(
                                AIMemoryItem.memory_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

            assert deleted == 1
            assert list(rows) == ["mem_new", "mem_visible"]
            assert ai_memory_embedding_store.get(memory_id="mem_old") is None

    asyncio.run(run())
