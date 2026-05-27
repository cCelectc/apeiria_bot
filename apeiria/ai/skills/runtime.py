"""Skill runtime: activation, progressive disclosure, and prompt injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from nonebot.log import logger

if TYPE_CHECKING:
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
    _file_definition: AISkillFileDefinition
    tags: tuple[str, ...] = ()

    @property
    def file_definition(self) -> AISkillFileDefinition:
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

    1. **Catalog management**: Maintain an index of file-based prompt skills.
    2. **Progressive disclosure**: Only expose name + description to the
       model.  Load full body on demand.
    3. **Selection projection**: Activate selected catalog names supplied by
       application planning.
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
                _file_definition=skill,
            )
        logger.debug(
            "Registered {} file-based skills into runtime catalog",
            len(skills),
        )

    def replace_file_skills(
        self,
        skills: list[AISkillFileDefinition],
    ) -> None:
        """Replace the full file-skill catalog atomically."""

        self._file_skills = {}
        self._catalog = {}
        self.register_file_skills(skills)

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
    # Selection projection
    # ------------------------------------------------------------------

    def build_selection_result(
        self,
        *,
        selected_names: list[str] | tuple[str, ...],
    ) -> AISkillSelectionResult:
        """Activate already selected skill names without model calls."""

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

            if activation.entry_mode in {"prompt_only", "workflow"}:
                section_lines.append(activation.body_markdown)
            if activation.tools:
                section_lines.append(f"\nRequired tools: {', '.join(activation.tools)}")

            sections.append("\n".join(section_lines))

        return "\n\n".join(sections)


ai_skill_runtime = AISkillRuntime()


__all__ = [
    "AISkillActivation",
    "AISkillCatalogEntry",
    "AISkillRuntime",
    "AISkillSelectionResult",
    "ai_skill_runtime",
]
