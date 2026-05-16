"""Social judgment prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .models import PromptPacket, PromptSection

if TYPE_CHECKING:
    from datetime import datetime

SocialEngagementType = Literal["direct", "ambient"]

_JSON_SHAPE = (
    '{"action":"reply|interject|wait|suppress",'
    '"tool_mode":"allow|avoid","reason_codes":["short_code"],'
    '"reason_text":"one short explanation","evidence":'
    '{"cooldown_active":false,"low_value_message":false}}'
)


@dataclass(frozen=True)
class SocialJudgmentPromptInput:
    """Prompt-facing materials for one social judgment call."""

    scene_type: str
    runtime_mode: str
    engagement_type: SocialEngagementType | str
    message_text: str
    latest_user_turn_text: str | None
    conversation_summary: str | None
    relationship_context: str | None
    persona_id: str | None
    available_tool_names: tuple[str, ...]
    recent_turn_count: int
    recent_bot_turn_count: int
    consecutive_silence_count: int
    current_time: "datetime"
    initiative_budget_score: float | None = None


def build_social_judgment_packet(
    inputs: SocialJudgmentPromptInput,
) -> PromptPacket:
    """Build a packet for deciding whether and how to speak."""

    sections = [
        PromptSection(
            role="system",
            name="Instruction",
            content="\n".join(
                (
                    "判断当前轮次的社交行为。",
                    "优先保证社交连贯、克制、人格一致，并避免显得像只会调用工具。",
                )
            ),
        ),
        PromptSection(
            role="system",
            name="EngagementPolicy",
            content=_build_engagement_policy(inputs),
        ),
        PromptSection(
            role="system",
            name="ActionPolicy",
            content="\n".join(
                (
                    "普通直接回应使用 action=reply。",
                    (
                        "只有在没有强直接点名但发言仍有明确社交价值时，"
                        "才使用 action=interject。"
                    ),
                    "如果现在应先停一下、但对话可能很快继续，使用 action=wait。",
                    "应该保持沉默时使用 action=suppress。",
                    "不要只为了延续对话而选择 reply 或 interject。",
                    "发言时，完整的短句也是有效回复；不要强行追加追问、邀约或延续钩子。",
                    "只有确实需要工具时才使用 tool_mode=allow；否则使用 avoid。",
                )
            ),
        ),
        PromptSection(
            role="user",
            name="Context",
            content=_build_context(inputs),
        ),
        PromptSection(
            role="user",
            name="OutputContract",
            content="\n".join(
                (
                    "只返回严格 JSON，格式如下：",
                    _JSON_SHAPE,
                )
            ),
        ),
    ]
    return PromptPacket(purpose="social_judgment", sections=tuple(sections))


def _build_engagement_policy(inputs: SocialJudgmentPromptInput) -> str:
    if inputs.engagement_type == "direct":
        return (
            "用户已经直接对机器人说话（@提及或私聊）。"
            "除非消息只是空泛填充、纯噪声或确实不值得回应，否则优先使用 action=reply；"
            "不值得回应时使用 action=suppress。"
        )
    return "\n".join(
        (
            (
                "机器人没有被直接点名。默认且最常见的动作应为 "
                "action=suppress（保持沉默）。"
                "只有在没有直接点名但发言仍有明确社交价值时，才使用 "
                "action=interject；也就是机器人确实有相关或合适的内容可以补充。"
            ),
            "不要仅仅因为机器人“能回答”就插话。真实群聊里，大多数时候人会保持沉默。",
        )
    )


def _build_context(inputs: SocialJudgmentPromptInput) -> str:
    tool_names = ", ".join(inputs.available_tool_names) or "<none>"
    lines = [
        f"场景类型: {inputs.scene_type}",
        f"运行模式: {inputs.runtime_mode}",
        f"互动类型: {inputs.engagement_type}",
        f"消息内容: {inputs.message_text}",
        f"最新用户发言: {inputs.latest_user_turn_text or '<none>'}",
        f"对话摘要: {inputs.conversation_summary or '<none>'}",
        f"关系上下文: {inputs.relationship_context or '<none>'}",
        f"人格 id: {inputs.persona_id or '<none>'}",
        f"可用工具名: {tool_names}",
        f"近期轮次数: {inputs.recent_turn_count}",
        f"近期机器人发言数: {inputs.recent_bot_turn_count}",
        f"连续沉默次数: {inputs.consecutive_silence_count}",
        f"当前时间: {inputs.current_time.isoformat()}",
    ]
    if inputs.initiative_budget_score is not None:
        lines.append(f"主动性预算分: {inputs.initiative_budget_score:.2f}")
    return "\n".join(lines)
