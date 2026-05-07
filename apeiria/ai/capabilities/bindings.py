"""Capability fulfillment bindings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AICapabilityBindingType(str, Enum):
    """Supported capability fulfillment mechanisms."""

    LOCAL_TOOL = "local_tool"
    HOST_ACTION = "host_action"
    PROMPT_SKILL = "prompt_skill"


AILocalToolHandler = Callable[..., Awaitable[Any]]
AIPromptSkillLoader = Callable[[], str]


@dataclass(frozen=True)
class AICapabilityBinding:
    """Runtime fulfillment for one capability contract."""

    contract_name: str
    binding_key: str
    binding_type: AICapabilityBindingType
    handler: AILocalToolHandler | None = None
    action_name: str | None = None
    load_prompt: AIPromptSkillLoader | None = None
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AICapabilityBindingSnapshot:
    """Immutable binding registry read model."""

    bindings: tuple[AICapabilityBinding, ...]
    by_key: Mapping[str, AICapabilityBinding]
    by_contract: Mapping[str, AICapabilityBinding]


def create_local_tool_binding(
    *,
    contract_name: str,
    binding_key: str,
    handler: AILocalToolHandler,
) -> AICapabilityBinding:
    """Create a local Python tool binding."""

    return AICapabilityBinding(
        contract_name=contract_name,
        binding_key=binding_key,
        binding_type=AICapabilityBindingType.LOCAL_TOOL,
        handler=handler,
    )


def create_host_action_binding(
    *,
    contract_name: str,
    binding_key: str,
    action_name: str,
    handler: AILocalToolHandler,
) -> AICapabilityBinding:
    """Create a host/plugin action binding."""

    return AICapabilityBinding(
        contract_name=contract_name,
        binding_key=binding_key,
        binding_type=AICapabilityBindingType.HOST_ACTION,
        action_name=action_name,
        handler=handler,
    )


def create_prompt_skill_binding(
    *,
    contract_name: str,
    binding_key: str,
    load_prompt: AIPromptSkillLoader,
    required_capabilities: tuple[str, ...] = (),
) -> AICapabilityBinding:
    """Create a prompt-skill activation binding."""

    return AICapabilityBinding(
        contract_name=contract_name,
        binding_key=binding_key,
        binding_type=AICapabilityBindingType.PROMPT_SKILL,
        load_prompt=load_prompt,
        required_capabilities=required_capabilities,
    )
