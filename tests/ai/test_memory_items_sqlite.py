from __future__ import annotations

import asyncio
import sys
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
    from apeiria.ai.memory.service import AIMemoryCreateInput, ai_memory_service

    async def scenario() -> None:
        created = await ai_memory_service.create_memory(
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

        duplicate = await ai_memory_service.create_memory_if_absent(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="preference",
                content="likes short answers",
            ),
        )
        assert duplicate is None

        recalled = await ai_memory_service.recall_memories(
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

        toggled = await ai_memory_service.toggle_memory_ignored(
            memory_id=created.memory_id,
        )
        assert toggled is not None
        assert toggled.is_ignored is True

        listed = await ai_memory_service.list_memories(
            anchor_type="user",
            anchor_id="user-1",
            include_ignored=True,
        )
        assert [item.memory_id for item in listed] == [created.memory_id]

        deleted = await ai_memory_service.delete_memory(
            memory_id=created.memory_id,
        )
        assert deleted is True
        assert await ai_memory_service.get_memory(memory_id=created.memory_id) is None

    asyncio.run(scenario())


def test_memory_admin_does_not_open_orm_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    stub_nonebot_plugin_orm = type(sys)("nonebot_plugin_orm")

    def unexpected_get_session() -> None:
        raise AssertionError

    stub_nonebot_plugin_orm.get_session = unexpected_get_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nonebot_plugin_orm", stub_nonebot_plugin_orm)

    from apeiria.ai.admin.memories import MemoriesAdminMixin

    class _Admin(MemoriesAdminMixin):
        pass

    async def scenario() -> None:
        memory = await _Admin().create_memory(
            memory_layer="long_term",
            memory_kind="note",
            anchor_type="user",
            anchor_id="user-1",
            content="operator note",
            salience=0.5,
            confidence=0.6,
        )
        assert memory.content == "operator note"

    asyncio.run(scenario())


def test_ignored_memory_retention_deletes_sqlite_rows_and_embedding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory.embedding_store import ai_memory_embedding_store
    from apeiria.ai.retention import AIRetentionService

    old_time = (datetime.now(timezone.utc) - timedelta(days=OLD_MEMORY_DAYS)).isoformat(
        timespec="seconds"
    )
    new_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with database_runtime.connect_sync() as connection:
        for memory_id, is_ignored, created_at in (
            ("mem_old", 1, old_time),
            ("mem_new", 1, new_time),
            ("mem_visible", 0, old_time),
        ):
            connection.execute(
                """
                INSERT INTO ai_memory_item (
                    memory_id,
                    anchor_type,
                    anchor_id,
                    memory_layer,
                    memory_kind,
                    content,
                    is_editable,
                    is_ignored,
                    salience,
                    confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    "user",
                    "user-1",
                    "knowledge",
                    "note",
                    memory_id,
                    1,
                    is_ignored,
                    0.5,
                    0.5,
                    created_at,
                ),
            )
    ai_memory_embedding_store.upsert(
        memory_id="mem_old",
        embedding_model="local",
        vector=[1.0],
    )

    deleted = AIRetentionService().cleanup_ignored_memories(
        retention_days=RETENTION_DAYS
    )

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            "SELECT memory_id FROM ai_memory_item ORDER BY memory_id"
        ).fetchall()
    assert deleted == 1
    assert rows == [("mem_new",), ("mem_visible",)]
    assert ai_memory_embedding_store.get(memory_id="mem_old") is None
