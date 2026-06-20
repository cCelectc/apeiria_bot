from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from apeiria.ai.model.registry import register_provider

_DEFAULT_MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
_CACHE_DIR = Path("data/fastembed_cache")


@register_provider("fastembed")
class FastEmbedProvider:
    capabilities: ClassVar[set[str]] = {"embedding"}

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name: str | None = None

    def _ensure_model(self, model_name: str | None = None) -> Any:
        target = model_name or _DEFAULT_MODEL
        if self._model is None or self._model_name != target:
            from fastembed import TextEmbedding

            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(
                model_name=target,
                cache_dir=str(_CACHE_DIR),
            )
            self._model_name = target
        return self._model

    async def embed(
        self,
        model_id: str,
        texts: list[str],
    ) -> list[list[float]]:
        import asyncio

        model = self._ensure_model(model_id if model_id != "fastembed" else None)
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, lambda: list(model.embed(texts)))
        return [e.tolist() for e in embeddings]
