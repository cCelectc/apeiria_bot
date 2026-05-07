from __future__ import annotations

import importlib

import pytest

from apeiria.ai.capabilities import (
    AICapabilityBindingType,
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
)


async def _handler(arguments: dict[str, object]) -> dict[str, object]:
    return arguments


def _contract(name: str) -> AICapabilityContract:
    return AICapabilityContract(
        name=name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description=f"{name} host action",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
    )


def test_host_action_registry_tracks_ready_and_incomplete_actions() -> None:
    from apeiria.ai.tools.host_actions import AIHostActionRegistry

    registry = AIHostActionRegistry()
    ready = registry.register_action(
        contract=_contract("plugin.inspect"),
        handler=_handler,
    )
    incomplete = registry.register_handler("plugin.partial", _handler)
    snapshot = registry.snapshot()

    assert ready.status == "ready"
    assert ready.contract is not None
    assert ready.binding is not None
    assert ready.binding.binding_type is AICapabilityBindingType.HOST_ACTION
    assert incomplete.status == "incomplete"
    assert incomplete.contract is None
    assert incomplete.binding is None
    assert tuple(record.action_name for record in snapshot.ready_actions) == (
        "plugin.inspect",
    )
    assert tuple(record.action_name for record in snapshot.incomplete_actions) == (
        "plugin.partial",
    )


def test_host_action_registry_rejects_incomplete_execution() -> None:
    from apeiria.ai.tools.host_actions import (
        AIHostActionRegistry,
        HostActionNotAllowedError,
    )

    registry = AIHostActionRegistry()
    registry.register_handler("plugin.partial", _handler)

    with pytest.raises(HostActionNotAllowedError):
        import asyncio

        asyncio.run(registry.invoke("plugin.partial"))


def test_old_nonebot_host_action_public_names_are_absent() -> None:
    tools_module = importlib.import_module("apeiria.ai.tools")
    models_module = importlib.import_module("apeiria.ai.tools.models")

    assert not hasattr(tools_module, "AINoneBotCapabilityRequest")
    assert not hasattr(models_module, "AINoneBotCapabilityRequest")


def test_legacy_tool_and_skill_primary_models_are_not_public() -> None:
    tools_module = importlib.import_module("apeiria.ai.tools")
    tool_models_module = importlib.import_module("apeiria.ai.tools.models")
    skills_module = importlib.import_module("apeiria.ai.skills")
    skill_catalog_module = importlib.import_module("apeiria.ai.skills.catalog")

    assert "AIToolSpec" not in tools_module.__all__
    assert "AISkillDefinition" not in skills_module.__all__
    assert not hasattr(tools_module, "AIToolSpec")
    assert not hasattr(tool_models_module, "AIToolSpec")
    assert not hasattr(skills_module, "AISkillDefinition")
    assert not hasattr(skill_catalog_module, "AISkillDefinition")
