"""Skill runtime: activation, progressive disclosure, and prompt injection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from nonebot.log import logger

if TYPE_CHECKING:
    from apeiria.ai.model.selection import AISelectedModel
    from apeiria.ai.skills.parser import AISkillFileDefinition

SkillActivationReason = Literal["model_selected", "explicit"]


@dataclass(frozen=True)
class AISkillCatalogEntry:
    """Lightweight catalog entry exposed to the model for progressive
    disclosure.

    Only ``skill_name`` and ``description`` are shown initially.
    The full ``body_markdown`` is loaded on activation.
    """

    skill_name: str
    description: str
    entry_mode: str
    origin: Literal["file", "tool"]
    tags: tuple[str, ...] = ()

    # Populated only for file-based skills
    _file_definition: AISkillFileDefinition | None = None

    @property
    def file_definition(self) -> AISkillFileDefinition | None:
        return self._file_definition


@dataclass(frozen=True)
class AISkillActivation:
    """An activated skill ready for prompt injection."""

    skill_name: str
    entry_mode: str
    body_markdown: str
    tools: tuple[str, ...]
    reason: SkillActivationReason


@dataclass(frozen=True)
class AISkillSelectionResult:
    """Outcome of LLM-based skill selection."""

    selected_names: tuple[str, ...]
    activations: tuple[AISkillActivation, ...]
    activation_prompt: str | None


_EMPTY_SELECTION = AISkillSelectionResult(
    selected_names=(),
    activations=(),
    activation_prompt=None,
)


class AISkillRuntime:
    """Runtime manager for skill catalog, activation, and prompt injection.

    Responsibilities:

    1. **Catalog management**: Maintain a unified index of file-based and
       tool-based skills.
    2. **Progressive disclosure**: Only expose name + description to the
       model.  Load full body on demand.
    3. **LLM-based selection**: Use a lightweight model call to decide
       which skills are relevant to a given message.
    4. **Prompt injection**: Build skill-specific prompt sections for
       activated skills.
    """

    def __init__(self) -> None:
        self._file_skills: dict[str, AISkillFileDefinition] = {}
        self._catalog: dict[str, AISkillCatalogEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_file_skills(
        self,
        skills: list[AISkillFileDefinition],
    ) -> None:
        """Register file-based skills into the catalog."""

        for skill in skills:
            self._file_skills[skill.skill_name] = skill
            self._catalog[skill.skill_name] = AISkillCatalogEntry(
                skill_name=skill.skill_name,
                description=skill.description,
                entry_mode=skill.entry_mode,
                tags=skill.tags,
                origin="file",
                _file_definition=skill,
            )
        logger.debug(
            "Registered {} file-based skills into runtime catalog",
            len(skills),
        )

    def register_tool_skill(
        self,
        *,
        skill_name: str,
        description: str,
        tags: tuple[str, ...] = (),
    ) -> None:
        """Register a tool-based skill entry (unified catalog view)."""

        if skill_name in self._catalog:
            return
        self._catalog[skill_name] = AISkillCatalogEntry(
            skill_name=skill_name,
            description=description,
            entry_mode="tool_backed",
            tags=tags,
            origin="tool",
        )

    # ------------------------------------------------------------------
    # Catalog queries
    # ------------------------------------------------------------------

    def list_catalog(self) -> list[AISkillCatalogEntry]:
        """Return all catalog entries sorted by name."""

        return sorted(self._catalog.values(), key=lambda e: e.skill_name)

    def list_file_skills(self) -> list[AISkillFileDefinition]:
        """Return all file-based skill definitions."""

        return sorted(self._file_skills.values(), key=lambda s: s.skill_name)

    def get_skill(self, skill_name: str) -> AISkillCatalogEntry | None:
        return self._catalog.get(skill_name)

    def has_file_skills(self) -> bool:
        """Return True if any file-based skills are registered."""

        return bool(self._file_skills)

    # ------------------------------------------------------------------
    # LLM-based skill selection
    # ------------------------------------------------------------------

    async def select_skills_for_message(
        self,
        *,
        message_text: str,
        conversation_summary: str | None,
    ) -> AISkillSelectionResult:
        """Use a lightweight LLM call to pick relevant file-based skills.

        Tool-based skills are always available via function calling and do
        not need explicit activation.  Only file-based skills (prompt_only,
        tool_backed with markdown body, workflow) require selection because
        their full body is injected into the prompt.

        Returns :data:`_EMPTY_SELECTION` when no file-based skills exist
        or the model cannot be reached.
        """

        file_entries = sorted(
            (entry for entry in self._catalog.values() if entry.origin == "file"),
            key=lambda entry: entry.skill_name,
        )
        if not file_entries:
            return _EMPTY_SELECTION

        catalog_prompt = self._build_catalog_prompt(file_entries)
        selected_names = await self._ask_model_for_skills(
            message_text=message_text,
            conversation_summary=conversation_summary,
            catalog_prompt=catalog_prompt,
            known_names={entry.skill_name for entry in file_entries},
        )

        activations: list[AISkillActivation] = []
        for name in selected_names:
            activation = self._activate_skill(name, reason="model_selected")
            if activation is not None:
                activations.append(activation)

        activation_prompt = self._build_activation_prompt(activations)
        return AISkillSelectionResult(
            selected_names=tuple(selected_names),
            activations=tuple(activations),
            activation_prompt=activation_prompt,
        )

    async def _ask_model_for_skills(
        self,
        *,
        message_text: str,
        conversation_summary: str | None,
        catalog_prompt: str,
        known_names: set[str],
    ) -> list[str]:
        """Call a lightweight model to classify which skills apply."""

        from apeiria.ai.model.gateway import model_gateway
        from apeiria.ai.model.models import AIModelRouteQuery

        selected: AISelectedModel | None = await model_gateway.select_model(
            query=AIModelRouteQuery(task_class="planner_light"),
        )
        if selected is None:
            return []

        prompt = _build_skill_selection_prompt(
            message_text=message_text,
            conversation_summary=conversation_summary,
            catalog_prompt=catalog_prompt,
        )
        try:
            response = await model_gateway.generate_native(
                selected=selected,
                prompt=prompt,
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

    # ------------------------------------------------------------------
    # Activation (progressive disclosure)
    # ------------------------------------------------------------------

    def _activate_skill(
        self,
        skill_name: str,
        *,
        reason: SkillActivationReason = "model_selected",
    ) -> AISkillActivation | None:
        entry = self._catalog.get(skill_name)
        if entry is None:
            return None

        if entry.origin == "file":
            file_def = self._file_skills.get(skill_name)
            if file_def is None:
                return None
            return AISkillActivation(
                skill_name=skill_name,
                entry_mode=file_def.entry_mode,
                body_markdown=file_def.body_markdown,
                tools=file_def.tools,
                reason=reason,
            )

        return AISkillActivation(
            skill_name=skill_name,
            entry_mode="tool_backed",
            body_markdown="",
            tools=(),
            reason=reason,
        )

    def activate_skill_explicit(
        self,
        skill_name: str,
    ) -> AISkillActivation | None:
        """Public entry for admin/test explicit activation."""

        return self._activate_skill(skill_name, reason="explicit")

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_catalog_prompt(
        entries: list[AISkillCatalogEntry],
    ) -> str:
        lines: list[str] = ["Available skills:"]
        for entry in entries:
            mode_tag = f"[{entry.entry_mode}]"
            lines.append(f"- **{entry.skill_name}** {mode_tag}: {entry.description}")
        return "\n".join(lines)

    @staticmethod
    def _build_activation_prompt(
        activations: list[AISkillActivation],
    ) -> str | None:
        if not activations:
            return None

        sections: list[str] = []
        for activation in activations:
            section_lines: list[str] = [
                f"## Active Skill: {activation.skill_name}",
            ]

            if activation.entry_mode == "prompt_only":
                section_lines.append(activation.body_markdown)
            elif activation.entry_mode == "tool_backed":
                if activation.body_markdown:
                    section_lines.append(activation.body_markdown)
                if activation.tools:
                    section_lines.append(
                        f"\nRequired tools: {', '.join(activation.tools)}"
                    )
            elif activation.entry_mode == "workflow":
                section_lines.append(activation.body_markdown)

            sections.append("\n".join(section_lines))

        return "\n\n".join(sections)


ai_skill_runtime = AISkillRuntime()


# ------------------------------------------------------------------
# Prompt for LLM skill selection
# ------------------------------------------------------------------


def _build_skill_selection_prompt(
    *,
    message_text: str,
    conversation_summary: str | None,
    catalog_prompt: str,
) -> str:
    parts: list[str] = [
        "You are a skill selector. Given the user message and "
        "available skills, decide which skills (if any) should be "
        "activated to help generate a good reply.",
        "",
        f"User message: {message_text}",
    ]
    if conversation_summary:
        parts.append(f"Conversation context: {conversation_summary}")
    parts.extend(
        [
            "",
            catalog_prompt,
            "",
            "Rules:",
            "- Only select skills that are clearly relevant.",
            "- Most messages need zero skills — return [] when unsure.",
            '- Return a JSON array of skill names, e.g. ["social-observer"] or [].',
            "- Return ONLY the JSON array, nothing else.",
        ]
    )
    return "\n".join(parts)


def _parse_skill_selection_response(
    content: str,
    *,
    known_names: set[str],
) -> list[str]:
    """Extract skill names from the model's JSON array response."""

    text = content.strip()

    # Find the JSON array in the response
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


__all__ = [
    "AISkillActivation",
    "AISkillCatalogEntry",
    "AISkillRuntime",
    "AISkillSelectionResult",
    "ai_skill_runtime",
]
