"""Skill-selection planning boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.model import AIModelRouteQuery, model_invoker
from apeiria.ai.model.routing.profile import ai_model_profile_service
from apeiria.ai.prompting import (
    SkillSelectionPromptInput,
    build_skill_selection_packet,
    render_messages,
)
from apeiria.ai.skills.runtime import AISkillSelectionResult, ai_skill_runtime
from apeiria.ai.skills.selection import parse_skill_selection_response
from apeiria.app.ai.auxiliary_structured_output import (
    SKILL_SELECTION_SCHEMA,
    auxiliary_json_schema_options,
)

if TYPE_CHECKING:
    from apeiria.ai.skills.runtime import AISkillCatalogEntry

_EMPTY_SELECTION = AISkillSelectionResult(
    selected_names=(),
    activations=(),
    activation_prompt=None,
)
_SKILL_SELECTION_OPTIONS = auxiliary_json_schema_options(
    name="skill_selection",
    schema=SKILL_SELECTION_SCHEMA,
)


async def select_runtime_skills(
    *,
    message_text: str,
    conversation_summary: str | None,
) -> "AISkillSelectionResult":
    """Select skills for a runtime turn through app-owned model orchestration."""

    entries = _file_catalog_entries()
    if not entries:
        return _EMPTY_SELECTION

    selected = await ai_model_profile_service.select_model(
        query=AIModelRouteQuery(task_class="planner_light"),
    )
    if selected is None:
        return _EMPTY_SELECTION

    known_names = {entry.skill_name for entry in entries}
    try:
        response = await model_invoker.generate_text(
            selected=selected,
            messages=render_messages(
                build_skill_selection_packet(
                    SkillSelectionPromptInput(
                        message_text=message_text,
                        conversation_summary=conversation_summary,
                        entries=entries,
                    )
                )
            ),
            options=_SKILL_SELECTION_OPTIONS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).debug("Skill selection model call failed")
        return _EMPTY_SELECTION
    if response is None:
        return _EMPTY_SELECTION

    selected_names = parse_skill_selection_response(
        response.content,
        known_names=known_names,
    )
    return ai_skill_runtime.build_selection_result(selected_names=selected_names)


def _file_catalog_entries() -> list["AISkillCatalogEntry"]:
    return sorted(
        ai_skill_runtime.list_catalog(),
        key=lambda entry: entry.skill_name,
    )


__all__ = ["select_runtime_skills"]
