from __future__ import annotations

from apeiria.ai.skills.catalog import get_skill_names
from apeiria.ai.types import PromptFragment, SessionContext


async def skills_context_handler(
    ctx: SessionContext,  # noqa: ARG001
) -> PromptFragment | None:
    skills = get_skill_names()
    if not skills:
        return None
    lines = [f"- {name}: {desc}" for name, desc in skills]
    content = (
        "你有以下技能可以使用。"
        "如需某个技能的详细内容，"
        "请调用 load_skill(name) 工具。\n" + "\n".join(lines)
    )
    return PromptFragment(
        role="system",
        content=content,
        placement="first",
    )
