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
            content="分析用户消息，并返回严格 JSON。",
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
                    "允许的 memory_kind 值："
                    "preference, fact, relationship, note, impression。",
                    (
                        "允许的 sentiment polarity 值：positive, neutral, "
                        "negative, playful。"
                    ),
                )
            ),
        ),
        PromptSection(
            role="system",
            name="MemoryExtractionRules",
            content="\n".join(
                (
                    "只包含未来对话中仍然有用的信息。",
                    "不要包含临时请求、玩笑或不确定猜测。",
                    "content 使用和原消息相同的语言。",
                    "某一行没有内容需要存储时，使用 action=noop。",
                    "当消息改变或更正已有持久记忆时，使用 action=update。",
                    (
                        "memory_kind=impression 用于关于用户性格、沟通风格或特质"
                        "的主观观察（例如热情、内向、知识面广）。"
                        "只有存在明确行为证据时才提取印象。"
                    ),
                    (
                        "scope_hint=user 用于跨场景的说话者事实或偏好；"
                        "participant 用于场景内关于说话者的事实或偏好；"
                        "scene 用于群、频道、项目或对话空间信息。"
                        "范围不确定时使用 auto。"
                    ),
                )
            ),
        ),
        PromptSection(
            role="system",
            name="SentimentRules",
            content="\n".join(
                (
                    "分析消息的整体情绪语气。",
                    (
                        "polarity: positive（感谢、开心、亲近），"
                        "negative（生气、烦躁、敌意），playful（调侃、玩笑、轻松），"
                        "neutral（信息性、平静、模糊）。"
                    ),
                    "intensity: 0.0（几乎不可察觉）到 1.0（非常强烈）。",
                )
            ),
        ),
        PromptSection(
            role="system",
            name="SelfIntroductionName",
            content=(
                "如果用户介绍了自己的称呼"
                '(e.g. "叫我小明", "I\'m Alice", "你可以喊我阿澈"), '
                "将名称提取到 self_introduction_name。否则填 null。"
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
                    '如果没有任何持久信息，返回 {"memories":[], '
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
