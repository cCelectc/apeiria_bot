from __future__ import annotations

import asyncio
from types import MappingProxyType, SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.capabilities import (
    AICapabilityBinding,
    AICapabilityBindingSnapshot,
    AICapabilityBindingType,
    AICapabilityContract,
    AICapabilityContractSnapshot,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
    create_local_tool_binding,
)
from apeiria.ai.tools import AIToolResult

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

EXPECTED_REGISTERED_TOOL_COUNT = 2


def _contract(name: str) -> AICapabilityContract:
    return AICapabilityContract(
        name=name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.PLUGIN,
        description=f"{name} description",
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
    )


def _tool_binding(contract: AICapabilityContract) -> AICapabilityBinding:
    async def handler(**_: Any) -> AIToolResult:
        return AIToolResult(summary="ok")

    return create_local_tool_binding(
        contract_name=contract.name,
        binding_key=f"plugin:{contract.name}",
        handler=handler,
    )


class _FakeToolRegistry:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.tools: dict[str, AICapabilityContract] = {}
        self.bindings: dict[str, AICapabilityBinding] = {}
        self.pending_tools = [_contract("app.future")]

    def register_contract_and_binding(
        self,
        *,
        contract: AICapabilityContract,
        binding: AICapabilityBinding,
    ) -> None:
        self._order.append(f"tool:{contract.name}")
        self.tools[contract.name] = contract
        self.bindings[binding.binding_key] = binding

    def list_tools(self) -> list[AICapabilityContract]:
        return [self.tools[name] for name in sorted(self.tools)]

    def register_pending_tools(self) -> int:
        self._order.append("pending_tools")
        count = 0
        for tool in self.pending_tools:
            if tool.name not in self.tools:
                self.tools[tool.name] = tool
                binding = _tool_binding(tool)
                self.bindings[binding.binding_key] = binding
                count += 1
        self.pending_tools = []
        return count

    def contract_snapshot(self) -> AICapabilityContractSnapshot:
        contracts = tuple(self.list_tools())
        return AICapabilityContractSnapshot(
            contracts=contracts,
            by_name=MappingProxyType(
                {contract.name: contract for contract in contracts}
            ),
        )

    def binding_snapshot(self) -> AICapabilityBindingSnapshot:
        bindings = tuple(self.bindings[key] for key in sorted(self.bindings))
        return AICapabilityBindingSnapshot(
            bindings=bindings,
            by_key=MappingProxyType(
                {binding.binding_key: binding for binding in bindings}
            ),
            by_contract=MappingProxyType(
                {binding.contract_name: binding for binding in bindings}
            ),
        )


class _FakeHostActionRegistry:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.handlers: dict[str, object] = {}
        self.contracts: dict[str, object] = {}

    def register_handler(self, action_name: str, handler: object) -> None:
        self._order.append(f"host_action:{action_name}")
        self.handlers[action_name] = handler

    def register_contract(self, contract: object) -> None:
        action_name = contract.name  # type: ignore[attr-defined]
        self._order.append(f"host_action_contract:{action_name}")
        self.contracts[action_name] = contract

    def register_action(self, *, contract: object, handler: object) -> None:
        action_name = contract.name  # type: ignore[attr-defined]
        self._order.append(f"host_action_ready:{action_name}")
        self.contracts[action_name] = contract
        self.handlers[action_name] = handler

    def list_actions(self) -> list[str]:
        return sorted({*self.handlers, *self.contracts})

    def snapshot(self) -> object:
        return SimpleNamespace(
            records=tuple(self._snapshot_record(name) for name in self.list_actions())
        )

    def _snapshot_record(self, action_name: str) -> SimpleNamespace:
        ready = action_name in self.handlers and action_name in self.contracts
        return SimpleNamespace(
            action_name=action_name,
            status="ready" if ready else "incomplete",
            contract=self.contracts.get(action_name),
            binding=(
                SimpleNamespace(
                    contract_name=action_name,
                    binding_key=f"host:{action_name}",
                    binding_type=AICapabilityBindingType.HOST_ACTION,
                )
                if ready
                else None
            ),
            reason=_incomplete_host_action_reason(
                action_name=action_name,
                has_handler=action_name in self.handlers,
            ),
        )


class _FakeToolService:
    def __init__(self, order: list[str]) -> None:
        self.registry = _FakeToolRegistry(order)
        self.host_action_registry = _FakeHostActionRegistry(order)


def _incomplete_host_action_reason(
    *,
    action_name: str,
    has_handler: bool,
) -> str | None:
    if action_name and not has_handler:
        return "missing host-action handler"
    if has_handler:
        return "missing capability contract"
    return None


class _FakeSkillService:
    def __init__(self, order: list[str], tool_service: _FakeToolService) -> None:
        self._order = order
        self._tool_service = tool_service
        self.calls: list[tuple[Path, ...]] = []
        self.visible_tool_names: list[tuple[str, ...]] = []
        self.skill_sources: tuple[Path, ...] = ()

    def ensure_initialized(
        self,
        *,
        skill_sources: tuple[Path, ...] = (),
    ) -> None:
        self._order.append("skills")
        self.calls.append(skill_sources)
        self.skill_sources = skill_sources
        self.visible_tool_names.append(
            tuple(tool.name for tool in self._tool_service.registry.list_tools())
        )

    def list_skills(self) -> list[object]:
        from apeiria.ai.skills.contracts import build_file_skill_metadata
        from apeiria.ai.skills.loader import load_skills_from_sources

        tool_skills = [
            SimpleNamespace(
                name=tool.name,
                description=tool.description,
                origin="tool",
            )
            for tool in self._tool_service.registry.list_tools()
        ]
        file_skills = [
            build_file_skill_metadata(skill)
            for skill in load_skills_from_sources(self.skill_sources)
        ]
        return [*tool_skills, *file_skills]


class _FakeFutureTaskService:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.calls = 0

    async def recover_scheduled_tasks(self) -> object:
        self.calls += 1
        self._order.append("future_recovery")
        return type(
            "RecoveryResult",
            (),
            {"rescheduled_task_ids": ("task-1",), "failed_task_ids": ()},
        )()


def test_lifecycle_applies_plugin_contributions_before_skill_sync(
    tmp_path: Path,
) -> None:
    from apeiria.ai.contributions import AIPluginContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    order: list[str] = []
    tool_service = _FakeToolService(order)
    skill_service = _FakeSkillService(order, tool_service)
    future_service = _FakeFutureTaskService(order)
    contributions = AIPluginContributionRegistry()
    skill_dir = tmp_path / "plugin" / "skills"

    tool_contract = _contract("plugin.echo")
    contributions.register_tool(
        contract=tool_contract,
        binding=_tool_binding(tool_contract),
    )
    contributions.register_host_action(
        contract=AICapabilityContract(
            name="plugin.echo",
            kind=AICapabilityKind.EXECUTABLE,
            origin=AICapabilityOrigin.PLUGIN,
            description="Echo plugin action.",
            safety=AICapabilitySafety(
                read_only=True,
                risk_level="low",
                concurrency_safe=True,
            ),
        ),
        handler=lambda _: {"ok": True},
    )
    contributions.register_host_action_handler(
        "plugin.partial",
        lambda _: {"ok": True},
    )
    contributions.register_capability_contract(
        AICapabilityContract(
            name="plugin.contract_only",
            kind=AICapabilityKind.EXECUTABLE,
            origin=AICapabilityOrigin.PLUGIN,
            description="Contract only plugin action.",
            safety=AICapabilitySafety(
                read_only=True,
                risk_level="low",
                concurrency_safe=True,
            ),
        )
    )
    contributions.register_skill_source(skill_dir)

    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=contributions,
        tool_service=tool_service,
        skill_service=skill_service,
        future_task_service=future_service,
        app_tool_loader=lambda: order.append("app_loader"),
    )

    asyncio.run(coordinator.startup())
    asyncio.run(coordinator.startup())

    assert order[:5] == [
        "app_loader",
        "pending_tools",
        "tool:plugin.echo",
        "host_action_ready:plugin.echo",
        "host_action:plugin.partial",
    ]
    assert "plugin.echo" in tool_service.registry.tools
    assert (
        tool_service.registry.tools["plugin.echo"].origin is AICapabilityOrigin.PLUGIN
    )
    assert tool_service.host_action_registry.list_actions() == [
        "plugin.contract_only",
        "plugin.echo",
        "plugin.partial",
    ]
    assert skill_service.calls[0] == (skill_dir.resolve(),)
    assert "plugin.echo" in skill_service.visible_tool_names[0]
    assert future_service.calls == 1
    assert len(tool_service.registry.tools) == EXPECTED_REGISTERED_TOOL_COUNT


def test_public_plugin_contribution_helpers_register_without_singleton_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import apeiria.ai.contributions as contribution_module
    from apeiria.ai.contributions import (
        AIPluginCapabilityContractInput,
        AIPluginContributionRegistry,
        register_ai_capability_contract,
        register_ai_host_action,
        register_ai_host_action_handler,
        register_ai_skill_source,
        register_ai_tool,
    )

    registry = AIPluginContributionRegistry()
    monkeypatch.setattr(contribution_module, "ai_plugin_contributions", registry)

    @register_ai_tool(
        name="plugin.echo",
        description="echo from a plugin",
        read_only=True,
        concurrency_safe=True,
    )
    async def echo_tool(message: str, *, context: object) -> AIToolResult:
        del message, context
        return AIToolResult(summary="ok")

    def capability_handler(arguments: dict[str, object]) -> dict[str, object]:
        return arguments

    plugin_dir = tmp_path / "plugin"
    skill_source = register_ai_skill_source("skills", base_path=plugin_dir)
    contract = register_ai_capability_contract(
        AIPluginCapabilityContractInput(
            name="plugin.echo",
            description="echo from a plugin",
            read_only=True,
            concurrency_safe=True,
        )
    )
    register_ai_host_action(
        contract=contract,
        handler=capability_handler,
    )
    register_ai_host_action_handler("plugin.partial", capability_handler)
    snapshot = registry.snapshot()

    assert echo_tool.__ai_tool_contract__.origin is AICapabilityOrigin.PLUGIN
    assert [tool.contract.name for tool in snapshot.tools] == ["plugin.echo"]
    assert snapshot.tools[0].contract.origin is AICapabilityOrigin.PLUGIN
    assert snapshot.tools[0].binding.contract_name == "plugin.echo"
    assert snapshot.capability_contracts[0].contract.name == "plugin.echo"
    assert snapshot.host_actions[0].contract.name == "plugin.echo"
    assert snapshot.host_action_handlers[0].action_name == "plugin.partial"
    assert snapshot.skill_sources[0].path == skill_source
    assert skill_source == (plugin_dir / "skills").resolve()


def test_plugin_skill_sources_skip_malformed_files(tmp_path: Path) -> None:
    from apeiria.ai.skills.loader import load_skills_from_sources

    valid_dir = tmp_path / "skills" / "valid"
    invalid_dir = tmp_path / "skills" / "invalid"
    valid_dir.mkdir(parents=True)
    invalid_dir.mkdir(parents=True)
    (valid_dir / "SKILL.md").write_text(
        """---
name: plugin.valid
description: valid skill
entry_mode: prompt_only
---

Use valid skill.
""",
        encoding="utf-8",
    )
    (invalid_dir / "SKILL.md").write_text("missing frontmatter", encoding="utf-8")

    skills = load_skills_from_sources((tmp_path / "skills",))

    assert [skill.skill_name for skill in skills] == ["plugin.valid"]
