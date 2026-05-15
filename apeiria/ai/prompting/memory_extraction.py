"""Memory extraction prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import PromptPacket, PromptSection

if TYPE_CHECKING:
    from apeiria.ai.memory.models import AIMemoryDefinition


@dataclass(frozen=True)
class MemoryExtractionPromptInput:
    """Prompt-facing materials for one memory extraction call."""

    message_text: str
    existing_memories: tuple["AIMemoryDefinition", ...] = ()


def build_memory_extraction_packet(
    inputs: MemoryExtractionPromptInput,
) -> PromptPacket:
    """Build a packet for extracting durable memory candidates."""

    sections: list[PromptSection] = [
        PromptSection(
            role="system",
            name="Instruction",
            content="Analyze the user message and return strict JSON.",
        ),
        PromptSection(
            role="system",
            name="OutputContract",
            content="\n".join(
                (
                    "{",
                    '  "memories": [{"memory_kind": "...", "content": "...",',
                    '    "action": "add|update|noop",',
                    '    "target_memory_id": "optional-existing-id",',
                    '    "scope_hint": "auto|scene|participant|user",',
                    '    "confidence": 0.0, "salience": 0.0}],',
                    '  "sentiment": {"polarity": "...", "intensity": 0.0},',
                    '  "self_introduction_name": null',
                    "}",
                    "",
                    "Allowed memory_kind values: "
                    "preference, fact, relationship, note, impression.",
                    (
                        "Allowed sentiment polarity values: positive, neutral, "
                        "negative, playful."
                    ),
                )
            ),
        ),
        PromptSection(
            role="system",
            name="MemoryExtractionRules",
            content="\n".join(
                (
                    "Only include information that is useful in future conversations.",
                    "Do not include transient requests, jokes, or uncertain guesses.",
                    "Use the same language as the source message for content.",
                    "Use action=noop when nothing should be stored for that row.",
                    (
                        "Use action=update when the message changes or corrects "
                        "an existing durable memory."
                    ),
                    (
                        "Use memory_kind=impression for subjective observations "
                        "about the user's personality, communication style, or "
                        "character traits (e.g. enthusiastic, introverted, "
                        "knowledgeable). Only extract impressions when there is "
                        "clear behavioral evidence."
                    ),
                    (
                        "Use scope_hint=user for durable facts or preferences about "
                        "the speaker across scenes, participant for scene-local "
                        "facts or preferences about the speaker, and scene for group, "
                        "channel, project, or conversation-space information. Use "
                        "auto when the best scope is unclear."
                    ),
                )
            ),
        ),
        PromptSection(
            role="system",
            name="SentimentRules",
            content="\n".join(
                (
                    "Analyze the overall emotional tone of the message.",
                    (
                        "polarity: positive (grateful, happy, affectionate), "
                        "negative (angry, annoyed, hostile), playful (teasing, "
                        "joking, lighthearted), neutral (informational, calm, "
                        "ambiguous)."
                    ),
                    "intensity: 0.0 (barely perceptible) to 1.0 (very strong).",
                )
            ),
        ),
        PromptSection(
            role="system",
            name="SelfIntroductionName",
            content=(
                "If the user introduces themselves by name "
                '(e.g. "叫我小明", "I\'m Alice", "你可以喊我阿澈"), '
                "extract the name into self_introduction_name. Otherwise null."
            ),
        ),
    ]
    existing = _format_existing_memories(inputs.existing_memories)
    if existing:
        sections.append(
            PromptSection(
                role="user",
                name="ExistingMemories",
                content=existing,
            )
        )
    sections.extend(
        (
            PromptSection(
                role="user",
                name="UserMessage",
                content=inputs.message_text,
            ),
            PromptSection(
                role="user",
                name="FallbackInstruction",
                content=(
                    'If there is nothing durable, return {"memories":[], '
                    '"sentiment": {"polarity": "neutral", "intensity": 0.0}, '
                    '"self_introduction_name": null}.'
                ),
            ),
        )
    )
    return PromptPacket(purpose="memory_extraction", sections=tuple(sections))


def _format_existing_memories(
    existing_memories: tuple["AIMemoryDefinition", ...],
) -> str | None:
    lines = [
        (
            f"- id={memory.memory_id}; kind={memory.memory_kind}; "
            f'content="{memory.content}"'
        )
        for memory in existing_memories[:8]
    ]
    return "\n".join(lines) if lines else None
