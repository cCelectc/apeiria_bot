"""Product-facing skill service built on top of the runtime tool layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.skills.contracts import build_skill_definition
from apeiria.app.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from apeiria.app.ai.skills.catalog import AISkillDefinition
    from apeiria.app.ai.tools.models import AIToolPolicy


class AISkillService:
    """Thin product-facing view over the underlying tool registry."""

    def list_skills(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AISkillDefinition"]:
        return [
            build_skill_definition(tool)
            for tool in ai_tool_service.list_tool_specs(policy)
        ]


ai_skill_service = AISkillService()

__all__ = ["AISkillService", "ai_skill_service"]
