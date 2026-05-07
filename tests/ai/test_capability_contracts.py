from __future__ import annotations

import pytest

from apeiria.ai.capabilities import (
    AICapabilityBindingRegistry,
    AICapabilityBindingType,
    AICapabilityContract,
    AICapabilityContractRegistry,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
    AIDuplicateCapabilityBindingError,
    AIDuplicateCapabilityContractError,
    create_host_action_binding,
    create_local_tool_binding,
    create_prompt_skill_binding,
)
from apeiria.ai.capabilities.adapters import (
    capability_contract_from_skill_definition,
    capability_contract_from_skill_file,
)
from apeiria.ai.skills.catalog import AISkillMetadata
from apeiria.ai.skills.parser import AISkillFileDefinition


async def _handler(**kwargs: object) -> object:
    return kwargs


def test_contracts_are_provider_neutral_metadata() -> None:
    contract = AICapabilityContract(
        name="memory.query",
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description="Search recalled memories.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
        tags=("memory", "read"),
        display_name="Memory query",
    )

    assert contract.version == 1
    assert contract.kind is AICapabilityKind.EXECUTABLE
    assert contract.origin is AICapabilityOrigin.BUILTIN
    assert contract.input_schema["properties"]["query"]["type"] == "string"
    assert contract.tags == ("memory", "read")
    assert not hasattr(contract, "handler")


def test_prompt_skill_contract_does_not_require_input_schema() -> None:
    contract = AICapabilityContract(
        name="writing-style",
        kind=AICapabilityKind.PROMPT_SKILL,
        origin=AICapabilityOrigin.SKILL,
        description="Apply a writing style.",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
    )

    assert contract.input_schema == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


def test_bindings_keep_handlers_outside_contracts() -> None:
    local = create_local_tool_binding(
        contract_name="memory.query",
        binding_key="local:memory.query",
        handler=_handler,
    )
    host = create_host_action_binding(
        contract_name="plugin.inspect",
        binding_key="host:plugin.inspect",
        action_name="plugin.inspect",
        handler=_handler,
    )
    prompt = create_prompt_skill_binding(
        contract_name="writing-style",
        binding_key="prompt:writing-style",
        load_prompt=lambda: "Write tersely.",
        required_capabilities=("memory.query",),
    )

    assert local.binding_type is AICapabilityBindingType.LOCAL_TOOL
    assert host.binding_type is AICapabilityBindingType.HOST_ACTION
    assert prompt.binding_type is AICapabilityBindingType.PROMPT_SKILL
    assert host.action_name == "plugin.inspect"
    assert prompt.required_capabilities == ("memory.query",)
    assert prompt.load_prompt() == "Write tersely."


def test_registries_validate_duplicates_and_return_immutable_snapshots() -> None:
    contract = AICapabilityContract(
        name="memory.query",
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description="Search recalled memories.",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
    )
    binding = create_local_tool_binding(
        contract_name=contract.name,
        binding_key="local:memory.query",
        handler=_handler,
    )
    contracts = AICapabilityContractRegistry()
    bindings = AICapabilityBindingRegistry()

    contracts.register(contract)
    bindings.register(binding)
    snapshot = contracts.snapshot()
    binding_snapshot = bindings.snapshot()

    assert snapshot.contracts == (contract,)
    assert snapshot.by_name[contract.name] == contract
    assert binding_snapshot.bindings == (binding,)
    assert binding_snapshot.by_contract[contract.name] == binding
    assert contracts.get(contract.name) == contract
    assert bindings.get_for_contract(contract.name) == binding

    with pytest.raises(AIDuplicateCapabilityContractError):
        contracts.register(contract)
    with pytest.raises(AIDuplicateCapabilityBindingError):
        bindings.register(binding)


def test_executable_contract_registers_with_local_binding() -> None:
    contract = AICapabilityContract(
        name="memory.query",
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description="Search recalled memories.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
        tags=("memory",),
    )
    binding = create_local_tool_binding(
        contract_name=contract.name,
        binding_key="local:memory.query",
        handler=_handler,
    )

    assert contract.name == "memory.query"
    assert contract.kind is AICapabilityKind.EXECUTABLE
    assert contract.origin is AICapabilityOrigin.BUILTIN
    assert contract.input_schema["required"] == ["query"]
    assert contract.safety.read_only is True
    assert contract.tags == ("memory",)
    assert binding.binding_type is AICapabilityBindingType.LOCAL_TOOL
    assert binding.handler is _handler


def test_host_action_contract_registers_with_host_action_binding() -> None:
    contract = AICapabilityContract(
        name="plugin.inspect",
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.PLUGIN,
        description="Inspect plugin state.",
        safety=AICapabilitySafety(
            read_only=False,
            risk_level="high",
            concurrency_safe=False,
        ),
    )
    binding = create_host_action_binding(
        contract_name=contract.name,
        binding_key="host:plugin.inspect",
        action_name="plugin.inspect",
        handler=_handler,
    )

    assert contract.origin is AICapabilityOrigin.PLUGIN
    assert binding.binding_type is AICapabilityBindingType.HOST_ACTION
    assert binding.action_name == "plugin.inspect"


def test_contracts_without_bindings_remain_inspectable_only() -> None:
    contract = AICapabilityContract(
        name="memory.query",
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description="Search recalled memories.",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
    )
    contracts = AICapabilityContractRegistry((contract,))
    bindings = AICapabilityBindingRegistry()

    assert tuple(contract.name for contract in contracts.snapshot().contracts) == (
        "memory.query",
    )
    assert bindings.snapshot().bindings == ()


def test_skill_definitions_adapt_to_prompt_skill_contracts() -> None:
    definition = AISkillMetadata(
        name="writing-style",
        description="Apply a writing style.",
        side_effect_level="read_only",
        permission_source="global",
        idempotent=True,
        fallback_behavior="skip",
        origin="file",
        entry_mode="prompt_only",
        tags=("writing",),
    )

    contract, binding = capability_contract_from_skill_definition(
        definition,
        load_prompt=lambda: "Write tersely.",
        required_capabilities=("memory.query",),
    )

    assert contract.name == "writing-style"
    assert contract.kind is AICapabilityKind.PROMPT_SKILL
    assert contract.origin is AICapabilityOrigin.SKILL
    assert contract.safety.risk_level == "low"
    assert contract.tags == ("writing",)
    assert binding.binding_type is AICapabilityBindingType.PROMPT_SKILL
    assert binding.load_prompt is not None
    assert binding.load_prompt() == "Write tersely."
    assert binding.required_capabilities == ("memory.query",)


def test_skill_file_definitions_adapt_to_prompt_skill_contracts() -> None:
    file_definition = AISkillFileDefinition(
        skill_name="plugin.skill",
        description="Plugin skill.",
        version=1,
        triggers=(),
        permissions=(),
        entry_mode="workflow",
        body_markdown="Use the plugin skill.",
        file_path="<test>",
        tools=("plugin.inspect",),
        tags=("plugin",),
    )

    contract, binding = capability_contract_from_skill_file(file_definition)

    assert contract.name == "plugin.skill"
    assert contract.kind is AICapabilityKind.PROMPT_SKILL
    assert contract.origin is AICapabilityOrigin.SKILL
    assert binding.load_prompt is not None
    assert binding.load_prompt() == "Use the plugin skill."
    assert binding.required_capabilities == ("plugin.inspect",)
