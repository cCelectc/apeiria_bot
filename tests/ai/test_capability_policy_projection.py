from __future__ import annotations

from apeiria.ai.capabilities import (
    AICapabilityBindingRegistry,
    AICapabilityContract,
    AICapabilityContractRegistry,
    AICapabilityExecutionContext,
    AICapabilityExposureContext,
    AICapabilityExposureProfile,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
    create_capability_exposure_plan,
    create_host_action_binding,
    create_local_tool_binding,
    create_prompt_skill_binding,
    evaluate_capability_execution,
    project_executable_contract,
)


async def _handler(**kwargs: object) -> object:
    return kwargs


def _tool_contract(
    name: str,
    *,
    risk_level: str = "low",
    read_only: bool = True,
) -> AICapabilityContract:
    return AICapabilityContract(
        name=name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.BUILTIN,
        description=f"{name} description",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        safety=AICapabilitySafety(
            read_only=read_only,
            risk_level=risk_level,
            concurrency_safe=True,
        ),
        tags=("test",),
    )


def _prompt_contract(name: str) -> AICapabilityContract:
    return AICapabilityContract(
        name=name,
        kind=AICapabilityKind.PROMPT_SKILL,
        origin=AICapabilityOrigin.SKILL,
        description=f"{name} prompt",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
    )


def test_exposure_plan_filters_and_records_non_exposure_reasons() -> None:
    allowed = _tool_contract("memory.query")
    denied = _tool_contract("memory.update", read_only=False)
    hidden = _tool_contract("internal.audit")
    unavailable = _tool_contract("future_task.manage")
    prompt = _prompt_contract("writing-style")
    contracts = AICapabilityContractRegistry(
        contracts=(allowed, denied, hidden, unavailable, prompt)
    )
    bindings = AICapabilityBindingRegistry(
        bindings=(
            create_local_tool_binding(
                contract_name=allowed.name,
                binding_key="local:memory.query",
                handler=_handler,
            ),
            create_local_tool_binding(
                contract_name=denied.name,
                binding_key="local:memory.update",
                handler=_handler,
            ),
            create_local_tool_binding(
                contract_name=hidden.name,
                binding_key="local:internal.audit",
                handler=_handler,
            ),
            create_prompt_skill_binding(
                contract_name=prompt.name,
                binding_key="prompt:writing-style",
                load_prompt=lambda: "Use direct language.",
            ),
        )
    )

    plan = create_capability_exposure_plan(
        contracts=contracts.snapshot(),
        bindings=bindings.snapshot(),
        context=AICapabilityExposureContext(
            profile=AICapabilityExposureProfile(
                execution_enabled=True,
                allowed_names=frozenset(
                    {allowed.name, denied.name, unavailable.name, prompt.name}
                ),
                denied_names=frozenset({denied.name}),
                hidden_names=frozenset({hidden.name}),
                active_prompt_skill_names=frozenset({prompt.name}),
            ),
            model_supports_tools=True,
        ),
    )

    assert tuple(tool.name for tool in plan.model_visible_tools) == ("memory_query",)
    assert plan.binding_map == {"memory.query": "local:memory.query"}
    assert tuple(activation.name for activation in plan.prompt_activations) == (
        "writing-style",
    )
    assert "explicitly denied" in plan.denied_reasons["memory.update"]
    assert "hidden" in plan.hidden_reasons["internal.audit"]
    assert "missing binding" in plan.unavailable_reasons["future_task.manage"]


def test_projection_uses_provider_neutral_model_tool_definition() -> None:
    definition = project_executable_contract(_tool_contract("memory.query"))

    assert definition.name == "memory_query"
    assert definition.description == "memory.query description"
    assert definition.parameters["required"] == ["query"]


def test_execution_gate_denies_stale_or_unavailable_binding() -> None:
    contract = _tool_contract("memory.update", read_only=False)
    binding = create_local_tool_binding(
        contract_name=contract.name,
        binding_key="local:memory.update",
        handler=_handler,
    )

    denied = evaluate_capability_execution(
        contract=contract,
        binding=binding,
        context=AICapabilityExecutionContext(
            profile=AICapabilityExposureProfile(
                execution_enabled=True,
                denied_names=frozenset({contract.name}),
            ),
        ),
    )
    missing = evaluate_capability_execution(
        contract=contract,
        binding=None,
        context=AICapabilityExecutionContext(
            profile=AICapabilityExposureProfile(execution_enabled=True),
        ),
    )

    assert denied.allowed is False
    assert denied.prompt_safe_observation == (
        "Capability 'memory.update' was not executed: explicitly denied."
    )
    assert missing.allowed is False
    assert "no executable binding" in missing.prompt_safe_observation


def test_execution_gate_denies_host_action_when_profile_disables_it() -> None:
    contract = _tool_contract("plugin.inspect")
    binding = create_host_action_binding(
        contract_name=contract.name,
        binding_key="host:plugin.inspect",
        action_name=contract.name,
        handler=_handler,
    )

    denied = evaluate_capability_execution(
        contract=contract,
        binding=binding,
        context=AICapabilityExecutionContext(
            profile=AICapabilityExposureProfile(
                execution_enabled=True,
                allow_host_actions=False,
            ),
        ),
    )

    assert denied.allowed is False
    assert denied.prompt_safe_observation == (
        "Capability 'plugin.inspect' was not executed: host actions are not enabled."
    )
