"""Model-backed skill selection."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.prompting import (
    SkillSelectionPromptInput,
    build_skill_selection_packet,
    render_messages,
)

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.skills.runtime import AISkillCatalogEntry


class AISkillSelector:
    """Select relevant file-based skills for a message."""

    async def select_skill_names(
        self,
        *,
        message_text: str,
        conversation_summary: str | None,
        entries: list["AISkillCatalogEntry"],
    ) -> list[str]:
        """Call a lightweight model to classify which skills apply."""

        from apeiria.ai.model.routing.models import AIModelRouteQuery
        from apeiria.ai.model.runtime.gateway import model_gateway

        selected: AISelectedModel | None = await model_gateway.select_model(
            query=AIModelRouteQuery(task_class="planner_light"),
        )
        if selected is None:
            return []

        known_names = {entry.skill_name for entry in entries}
        try:
            response = await model_gateway.generate_native(
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
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).debug("Skill selection model call failed")
            return []
        if response is None:
            return []

        return _parse_skill_selection_response(
            response.content,
            known_names=known_names,
        )


def _parse_skill_selection_response(
    content: str,
    *,
    known_names: set[str],
) -> list[str]:
    """Extract skill names from the model's JSON array response."""

    text = content.strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    selected_names: list[str] = []
    seen_names: set[str] = set()
    for name in parsed:
        if not isinstance(name, str):
            continue
        if name not in known_names or name in seen_names:
            continue
        selected_names.append(name)
        seen_names.add(name)
    return selected_names


__all__ = ["AISkillSelector"]
