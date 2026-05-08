"""Runtime memory extraction model step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.memory import AIMemoryExtractionResult, AIMessageSentiment
from apeiria.ai.memory.extraction import parse_memory_extraction_response
from apeiria.ai.model import AIModelRouteQuery, model_invoker
from apeiria.ai.model.routing.profile import ai_model_profile_service
from apeiria.ai.prompting import (
    MemoryExtractionPromptInput,
    build_memory_extraction_packet,
    render_messages,
)
from apeiria.app.ai.auxiliary_structured_output import (
    MEMORY_EXTRACTION_SCHEMA,
    auxiliary_json_schema_options,
)

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition


_DEFAULT_EXTRACTION_RESULT = AIMemoryExtractionResult(
    candidates=[],
    sentiment=AIMessageSentiment(polarity="neutral", intensity=0.0),
    self_introduction_name=None,
)
_MEMORY_EXTRACTION_OPTIONS = auxiliary_json_schema_options(
    name="memory_extraction",
    schema=MEMORY_EXTRACTION_SCHEMA,
)


async def extract_memory_from_message(
    *,
    message_text: str,
    existing_memories: tuple["AIMemoryDefinition", ...],
) -> AIMemoryExtractionResult:
    selected = await ai_model_profile_service.select_model(
        query=AIModelRouteQuery(task_class="memory_extraction"),
    )
    if selected is None:
        return _DEFAULT_EXTRACTION_RESULT

    try:
        response = await model_invoker.generate_text(
            selected=selected,
            messages=render_messages(
                build_memory_extraction_packet(
                    MemoryExtractionPromptInput(
                        message_text=message_text,
                        existing_memories=existing_memories,
                    )
                )
            ),
            options=_MEMORY_EXTRACTION_OPTIONS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning("AI memory extraction failed")
        return _DEFAULT_EXTRACTION_RESULT
    if response is None:
        return _DEFAULT_EXTRACTION_RESULT
    return parse_memory_extraction_response(response.content)
