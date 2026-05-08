from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_chunk_embedding_store_writes_separate_files(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)

    from apeiria.ai.knowledge.embedding_store import ChunkEmbeddingStore

    store = ChunkEmbeddingStore()
    created = store.upsert(
        chunk_id="kchunk_doc_1_0",
        embedding_model="local_bigrams_v1",
        vector=[0.2, 0.8],
    )

    loaded = store.get(chunk_id="kchunk_doc_1_0")

    assert loaded == created
    assert (
        tmp_path / "data" / "ai" / "knowledge_chunk_embeddings" / "kchunk_doc_1_0.json"
    ).is_file()
    assert not (tmp_path / "data" / "ai" / "memory_embeddings").exists()

    assert store.delete(chunk_id="kchunk_doc_1_0") is True
    assert store.get(chunk_id="kchunk_doc_1_0") is None
