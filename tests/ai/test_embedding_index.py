from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

os.environ.setdefault("FAISS_NO_GPU", "1")

import apeiria.ai.embedding.index as idx_mod
from apeiria.ai.embedding.index import VectorIndex


def _with_data_dir(tmp_path: Path):
    old_dir = idx_mod._DATA_DIR
    idx_mod._DATA_DIR = tmp_path

    class _Ctx:
        def __enter__(self) -> None:
            pass

        def __exit__(self, *_: object) -> None:
            idx_mod._DATA_DIR = old_dir

    return _Ctx()


def test_vector_index_add_and_search(tmp_path: Path) -> None:
    with _with_data_dir(tmp_path):
        index = VectorIndex("test_collection", 4)
        index.load()
        v1 = [1.0, 0.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0, 0.0]
        index.add([1, 2], [v1, v2])
        results = index.search([0.9, 0.1, 0.0, 0.0], top_k=2)
        assert len(results) >= 1
        assert results[0][0] == 1
        assert (tmp_path / "test_collection" / "index.faiss").exists()


def test_vector_index_rebuild(tmp_path: Path) -> None:
    with _with_data_dir(tmp_path):
        index = VectorIndex("rebuild_test", 3)
        index.load()
        index.add([10, 20], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        index.rebuild([30], [[0.0, 0.0, 1.0]])
        results = index.search([0.0, 0.0, 1.0], top_k=1)
        assert results[0][0] == 30  # noqa: PLR2004


def test_empty_index_search(tmp_path: Path) -> None:
    with _with_data_dir(tmp_path):
        index = VectorIndex("empty", 4)
        index.load()
        results = index.search([1.0, 0.0, 0.0, 0.0])
        assert results == []


def test_vector_index_remove(tmp_path: Path) -> None:
    with _with_data_dir(tmp_path):
        index = VectorIndex("remove_test", 3)
        index.load()
        index.add([1, 2, 3], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        index.remove([2])
        results = index.search([0.0, 1.0, 0.0], top_k=3)
        result_ids = [r[0] for r in results]
        assert 2 not in result_ids  # noqa: PLR2004


def test_vector_index_persistence(tmp_path: Path) -> None:
    with _with_data_dir(tmp_path):
        index = VectorIndex("persist_test", 3)
        index.load()
        index.add([42], [[1.0, 0.0, 0.0]])

    with _with_data_dir(tmp_path):
        index2 = VectorIndex("persist_test", 3)
        index2.load()
        results = index2.search([1.0, 0.0, 0.0], top_k=1)
        assert results[0][0] == 42  # noqa: PLR2004
