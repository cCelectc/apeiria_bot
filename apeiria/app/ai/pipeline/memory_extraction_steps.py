"""Runtime memory extraction model step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.memory import AIMemoryExtractionResult, AIMessageSentiment
from apeiria.ai.memory.extraction import (
    build_memory_extraction_prompt,
    parse_memory_extraction_response,
)
from apeiria.ai.model import AIModelRouteQuery, model_gateway

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition


_DEFAULT_EXTRACTION_RESULT = AIMemoryExtractionResult(
    candidates=[],
    sentiment=AIMessageSentiment(polarity="neutral", intensity=0.0),
    self_introduction_name=None,
)


async def extract_memory_from_message(
    *,
    message_text: str,
    existing_memories: tuple["AIMemoryDefinition", ...],
) -> AIMemoryExtractionResult:
    selected = await model_gateway.select_model(
        query=AIModelRouteQuery(task_class="memory_extraction"),
    )
    if selected is None:
        return _DEFAULT_EXTRACTION_RESULT

    try:
        response = await model_gateway.generate_native(
            selected=selected,
            prompt=build_memory_extraction_prompt(
                message_text,
                existing_memories=existing_memories,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning("AI memory extraction failed")
        return _DEFAULT_EXTRACTION_RESULT
    if response is None:
        return _DEFAULT_EXTRACTION_RESULT
    return parse_memory_extraction_response(response.content)
