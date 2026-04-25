from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_memory_embedding_store_writes_files(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.ai.memory.embedding_store import ai_memory_embedding_store

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)

    created = ai_memory_embedding_store.upsert(
        memory_id="mem_1",
        embedding_model="local_bigrams_v1",
        vector=[0.25, 0.75],
    )
    loaded = ai_memory_embedding_store.get(memory_id="mem_1")

    assert loaded == created
    assert (tmp_path / "data" / "ai" / "memory_embeddings" / "mem_1.json").is_file()
    assert ai_memory_embedding_store.delete(memory_id="mem_1") is True
    assert ai_memory_embedding_store.get(memory_id="mem_1") is None
