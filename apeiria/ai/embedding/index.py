from __future__ import annotations

import asyncio
import json
from pathlib import Path

import faiss
import numpy as np
from nonebot.log import logger

_DATA_DIR = Path("data/embeddings")


class VectorIndex:
    def __init__(self, collection: str, dimensions: int) -> None:
        self._collection = collection
        self._dimensions = dimensions
        self._dir = _DATA_DIR / collection
        self._index: faiss.IndexIDMap | None = None
        self._rebuild_running = False
        self._pending_rebuild: tuple[list[int], list[list[float]]] | None = None
        self._lock = asyncio.Lock()

    def _index_path(self) -> Path:
        return self._dir / "index.faiss"

    def _meta_path(self) -> Path:
        return self._dir / "meta.json"

    def load(self) -> None:
        meta_path = self._meta_path()
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                stored_dims = meta.get("dimensions")
                if isinstance(stored_dims, int) and stored_dims > 0:
                    self._dimensions = stored_dims
            except (json.JSONDecodeError, OSError):
                pass

        path = self._index_path()
        if path.exists():
            try:
                self._index = faiss.read_index(str(path))
            except (RuntimeError, OSError):
                logger.warning("Corrupt FAISS index at {}, rebuilding", path)
            else:
                return
        base = faiss.IndexFlatIP(self._dimensions)
        self._index = faiss.IndexIDMap(base)

    def _ensure_loaded(self) -> faiss.IndexIDMap:
        if self._index is None:
            self.load()
        assert self._index is not None
        return self._index

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        index = self._ensure_loaded()
        if index.ntotal == 0:
            return []
        vec = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(vec)
        scores, ids = index.search(vec, min(top_k, index.ntotal))
        return [
            (int(ids[0][i]), float(scores[0][i]))
            for i in range(len(ids[0]))
            if ids[0][i] != -1
        ]

    def add(self, ids: list[int], vectors: list[list[float]]) -> None:
        index = self._ensure_loaded()
        arr = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(arr)
        id_arr = np.array(ids, dtype=np.int64)
        index.add_with_ids(arr, id_arr)
        self._persist()

    def remove(self, ids: list[int]) -> None:
        index = self._ensure_loaded()
        id_arr = np.array(ids, dtype=np.int64)
        index.remove_ids(id_arr)
        self._persist()

    def rebuild(self, ids: list[int], vectors: list[list[float]]) -> None:
        base = faiss.IndexFlatIP(self._dimensions)
        new_index = faiss.IndexIDMap(base)
        if ids and vectors:
            arr = np.array(vectors, dtype=np.float32)
            faiss.normalize_L2(arr)
            id_arr = np.array(ids, dtype=np.int64)
            new_index.add_with_ids(arr, id_arr)
        self._index = new_index
        self._persist()

    def _persist(self) -> None:
        index = self._ensure_loaded()
        self._dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self._index_path()))
        meta = {
            "collection": self._collection,
            "dimensions": self._dimensions,
            "vector_count": index.ntotal,
        }
        self._meta_path().write_text(json.dumps(meta))

    async def async_rebuild(self, ids: list[int], vectors: list[list[float]]) -> None:
        async with self._lock:
            self._pending_rebuild = (ids, vectors)
            if self._rebuild_running:
                return
            self._rebuild_running = True

        try:
            while True:
                async with self._lock:
                    data = self._pending_rebuild
                    self._pending_rebuild = None
                if data is None:
                    break
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.rebuild, data[0], data[1])
        finally:
            self._rebuild_running = False
