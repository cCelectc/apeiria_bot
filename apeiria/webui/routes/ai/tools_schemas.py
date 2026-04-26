"""Schema models for AI tool and capability routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.skills import AISkillDefinition
    from apeiria.ai.tools import (
        AICapabilityDefinition,
        AICapabilityPreview,
        AIToolExecutionView,
        AIToolIntentPreview,
        AIToolPolicy,
        AIToolPolicyBindingSpec,
        AIToolSpec,
    )


class AIToolItem(BaseModel):
    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    risk_level: str
    is_capability_bridge: bool = False


class AISkillItem(BaseModel):
    name: str
    description: str
    display_name: str
    display_description: str
    read_only: bool
    concurrency_safe: bool
    risk_level: str
    risk_label: str
    is_capability_bridge: bool = False


class AIToolExecutionItem(BaseModel):
    execution_id: str
    session_id: str
    tool_name: str
    status: str
    input_json: str | None = None
    output_json: str | None = None
    created_at: str


class AIToolPolicyPreviewRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AIToolIntentPreviewRequest(BaseModel):
    message_text: str = Field(min_length=1, max_length=2000)
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AIToolIntentPreviewItem(BaseModel):
    tool_name: str
    kind: str
    reason: str | None = None
    input_payload: object | None = None


class AIToolPolicyPreviewItem(BaseModel):
    execution_enabled: bool
    allowed_tool_names: list[str] | None = None
    denied_tool_names: list[str] = []
    allow_high_risk_tools: bool
    allow_capability_bridge: bool


class AIToolPolicyBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    allow_read_only_tools: bool
    capability_mode: str


class AIToolPolicyBindingCreateRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=32)
    scope_id: str = Field(min_length=1, max_length=128)
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AIToolPolicyBindingUpdateRequest(BaseModel):
    binding_id: str = Field(min_length=1, max_length=64)
    allow_read_only_tools: bool
    capability_mode: str = Field(min_length=1, max_length=32)


class AICapabilityPreviewRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128)
    scope_type: str = Field(min_length=1, max_length=32)
    is_tome: bool = False
    allow_read_only_tools: bool = True
    capability_mode: str = Field(default="off", min_length=1, max_length=32)


class AICapabilityPreviewItem(BaseModel):
    capability_name: str
    registered: bool
    allowed: bool
    reason: str
    allow_capability_bridge: bool
    execution_enabled: bool


class AICapabilityItem(BaseModel):
    capability_name: str
    bound_tool_name: str


def _skill_display_name(skill_name: str) -> str:
    return {
        "future_task.manage": "提醒与任务",
        "memory.query": "查询记忆",
        "memory.update": "修正记忆",
        "plugin.capability": "调用插件能力",
        "relationship.inspect": "查看关系状态",
    }.get(skill_name, skill_name)


def _skill_display_description(skill_name: str, fallback: str) -> str:
    return {
        "future_task.manage": "创建、取消或查看机器人已安排的提醒任务。",
        "memory.query": "查看机器人为当前用户或会话召回的长期记忆内容。",
        "memory.update": "修正当前会话中已召回的长期记忆内容。",
        "plugin.capability": "在允许范围内调用 NoneBot 插件能力。",
        "relationship.inspect": "查看机器人对当前用户关系状态与情绪倾向的理解。",
    }.get(skill_name, fallback)


def _skill_risk_label(risk_level: str) -> str:
    return {
        "low": "低风险",
        "medium": "中风险",
        "high": "高风险",
    }.get(risk_level, risk_level)


def to_ai_tool_item(item: "AIToolSpec") -> AIToolItem:
    return AIToolItem(
        name=item.name,
        description=item.description,
        read_only=item.read_only,
        concurrency_safe=item.concurrency_safe,
        risk_level=item.risk_level,
        is_capability_bridge=item.is_capability_bridge,
    )


def to_ai_skill_item(item: "AISkillDefinition") -> AISkillItem:
    risk_level = (
        "high"
        if item.contract.side_effect_level == "high_risk"
        else "low"
        if item.contract.side_effect_level == "read_only"
        else "medium"
    )
    return AISkillItem(
        name=item.skill_name,
        description=item.description,
        display_name=_skill_display_name(item.skill_name),
        display_description=_skill_display_description(
            item.skill_name,
            item.description,
        ),
        read_only=item.contract.side_effect_level == "read_only",
        concurrency_safe=item.contract.idempotency == "idempotent",
        risk_level=risk_level,
        risk_label=_skill_risk_label(risk_level),
        is_capability_bridge=item.skill_name == "plugin.capability",
    )


def to_ai_tool_execution_item(item: "AIToolExecutionView") -> AIToolExecutionItem:
    return AIToolExecutionItem(
        execution_id=item.execution_id,
        session_id=item.session_id,
        tool_name=item.tool_name,
        status=item.status,
        input_json=item.input_json,
        output_json=item.output_json,
        created_at=item.created_at.isoformat(),
    )


def to_ai_tool_intent_preview_item(
    item: "AIToolIntentPreview",
) -> AIToolIntentPreviewItem:
    return AIToolIntentPreviewItem(
        tool_name=item.tool_name,
        kind=item.kind,
        reason=item.reason,
        input_payload=item.input_payload,
    )


def to_ai_tool_policy_preview_item(item: "AIToolPolicy") -> AIToolPolicyPreviewItem:
    return AIToolPolicyPreviewItem(
        execution_enabled=item.execution_enabled,
        allowed_tool_names=(
            sorted(item.allowed_tool_names)
            if item.allowed_tool_names is not None
            else None
        ),
        denied_tool_names=sorted(item.denied_tool_names),
        allow_high_risk_tools=item.allow_high_risk_tools,
        allow_capability_bridge=item.allow_capability_bridge,
    )


def to_ai_tool_policy_binding_item(
    item: "AIToolPolicyBindingSpec",
) -> AIToolPolicyBindingItem:
    return AIToolPolicyBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        allow_read_only_tools=item.allow_read_only_tools,
        capability_mode=item.capability_mode,
    )


def to_ai_capability_preview_item(
    item: "AICapabilityPreview",
) -> AICapabilityPreviewItem:
    return AICapabilityPreviewItem(
        capability_name=item.capability_name,
        registered=item.registered,
        allowed=item.allowed,
        reason=item.reason,
        allow_capability_bridge=item.allow_capability_bridge,
        execution_enabled=item.execution_enabled,
    )


def to_ai_capability_item(item: "AICapabilityDefinition") -> AICapabilityItem:
    return AICapabilityItem(
        capability_name=item.capability_name,
        bound_tool_name=item.bound_tool_name,
    )
