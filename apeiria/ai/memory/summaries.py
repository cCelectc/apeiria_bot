"""Summary memory maintenance for AI memory anchors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.memory.contracts import AIMemoryCreateInput, AIMemoryUpdateInput
from apeiria.ai.memory.summary import build_summary_memory_content

if TYPE_CHECKING:
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryKind,
        AIMemoryLayer,
    )
    from apeiria.ai.memory.repository import AIMemoryRepository


class MemorySummaryCoordinator:
    """Own deterministic summary creation, refresh, and cleanup."""

    SUMMARY_MEMORY_LAYER: AIMemoryLayer = "summary"
    SUMMARY_MEMORY_KIND: AIMemoryKind = "note"

    def __init__(self, repository: AIMemoryRepository) -> None:
        self._repository = repository

    async def consolidate_anchor_summary(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
    ) -> None:
        memories = self._repository.list_memories(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            lifecycle_states=(),
        )
        summary_content = build_summary_memory_content(memories)
        existing_summary = next(
            (
                memory
                for memory in memories
                if memory.memory_layer == self.SUMMARY_MEMORY_LAYER
            ),
            None,
        )

        if summary_content is None:
            if existing_summary is not None:
                self._repository.delete_memory(memory_id=existing_summary.memory_id)
            return

        if existing_summary is not None:
            if existing_summary.content == summary_content:
                return
            self._repository.update_memory_content(
                memory_id=existing_summary.memory_id,
                update_input=AIMemoryUpdateInput(
                    content=summary_content,
                    salience=0.8,
                    confidence=0.85,
                    source_message_id=existing_summary.source_message_id,
                ),
            )
            return

        self._repository.create_memory(
            AIMemoryCreateInput(
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                memory_layer=self.SUMMARY_MEMORY_LAYER,
                memory_kind=self.SUMMARY_MEMORY_KIND,
                content=summary_content,
                is_editable=False,
                salience=0.8,
                confidence=0.85,
            ),
            ignore_existing=False,
        )
