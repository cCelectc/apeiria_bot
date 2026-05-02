from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apeiria.ai.tools import AIToolResult, AIToolSpec

if TYPE_CHECKING:
    import pytest

EXPECTED_REGISTERED_TOOL_COUNT = 2


def _tool(name: str) -> AIToolSpec:
    async def handler(**_: Any) -> AIToolResult:
        return AIToolResult(summary="ok")

    return AIToolSpec(
        name=name,
        description=f"{name} description",
        read_only=True,
        concurrency_safe=True,
        entrypoint=handler,
        origin="plugin",
    )


class _FakeToolRegistry:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.tools: dict[str, AIToolSpec] = {}
        self.pending_tools = [_tool("app.future")]

    def register(self, tool: AIToolSpec) -> None:
        self._order.append(f"tool:{tool.name}")
        self.tools[tool.name] = tool

    def list_tools(self) -> list[AIToolSpec]:
        return [self.tools[name] for name in sorted(self.tools)]

    def register_pending_tools(self) -> int:
        self._order.append("pending_tools")
        count = 0
        for tool in self.pending_tools:
            if tool.name not in self.tools:
                self.tools[tool.name] = tool
                count += 1
        self.pending_tools = []
        return count


class _FakeCapabilityBridge:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.handlers: dict[str, object] = {}

    def register(self, capability_name: str, handler: object) -> None:
        self._order.append(f"capability:{capability_name}")
        self.handlers[capability_name] = handler

    def list_capabilities(self) -> list[str]:
        return sorted(self.handlers)


class _FakeToolService:
    def __init__(self, order: list[str]) -> None:
        self.registry = _FakeToolRegistry(order)
        self.capability_bridge = _FakeCapabilityBridge(order)


class _FakeSkillService:
    def __init__(self, order: list[str], tool_service: _FakeToolService) -> None:
        self._order = order
        self._tool_service = tool_service
        self.calls: list[tuple[Path, ...]] = []
        self.visible_tool_names: list[tuple[str, ...]] = []

    def ensure_initialized(
        self,
        *,
        skill_sources: tuple[Path, ...] = (),
    ) -> None:
        self._order.append("skills")
        self.calls.append(skill_sources)
        self.visible_tool_names.append(
            tuple(tool.name for tool in self._tool_service.registry.list_tools())
        )


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
    contributions.register_tool(_tool("plugin.echo"))
    contributions.register_capability_handler("plugin.echo", lambda _: {"ok": True})
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
        "capability:plugin.echo",
        "skills",
    ]
    assert "plugin.echo" in tool_service.registry.tools
    assert tool_service.registry.tools["plugin.echo"].origin == "plugin"
    assert tool_service.capability_bridge.list_capabilities() == ["plugin.echo"]
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
        AIPluginContributionRegistry,
        register_ai_capability_handler,
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
    register_ai_capability_handler("plugin.echo", capability_handler)
    snapshot = registry.snapshot()

    assert echo_tool.__ai_tool_spec__.origin == "plugin"  # type: ignore[attr-defined]
    assert [tool.name for tool in snapshot.tools] == ["plugin.echo"]
    assert snapshot.tools[0].origin == "plugin"
    assert snapshot.capability_handlers[0].capability_name == "plugin.echo"
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


def test_runtime_readiness_reports_lifecycle_dependencies_without_initializing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apeiria.app.ai.lifecycle as lifecycle_module
    from apeiria.ai.service import AIRuntimeReadinessProbe
    from apeiria.app.ai.lifecycle import (
        AILifecycleComponentStatus,
        AILifecycleSnapshot,
    )

    class _LifecycleProbe:
        def __init__(self) -> None:
            self.inspect_calls = 0
            self.startup_calls = 0

        def inspect(self) -> AILifecycleSnapshot:
            self.inspect_calls += 1
            return AILifecycleSnapshot(
                initialized=False,
                initialization_source="not_initialized",
                components=(
                    AILifecycleComponentStatus(
                        key="tool_registry",
                        available=False,
                        detail="not_initialized",
                        next_step="Load the AI plugin startup lifecycle hook.",
                    ),
                    AILifecycleComponentStatus(
                        key="skill_catalog",
                        available=False,
                        detail="not_initialized",
                        next_step="Load the AI plugin startup lifecycle hook.",
                    ),
                    AILifecycleComponentStatus(
                        key="capability_bridge",
                        available=False,
                        detail="not_initialized",
                        next_step="Load the AI plugin startup lifecycle hook.",
                    ),
                ),
            )

        async def startup(self) -> None:
            self.startup_calls += 1
            raise AssertionError

        def ensure_runtime_support_initialized(self, **_: object) -> object:
            raise AssertionError

    fake = _LifecycleProbe()
    monkeypatch.setattr(lifecycle_module, "ai_lifecycle_coordinator", fake)

    statuses = {item.key: item for item in AIRuntimeReadinessProbe().inspect()}

    assert statuses["tool_registry"].available is False
    assert statuses["skill_catalog"].available is False
    assert statuses["capability_bridge"].available is False
    assert statuses["tool_registry"].detail == "not_initialized"
    assert fake.inspect_calls == 1
    assert fake.startup_calls == 0


def test_ai_plugin_command_surface_is_unchanged() -> None:
    spec = importlib.util.find_spec("apeiria.builtin_plugins.ai")
    assert spec is not None
    assert spec.origin is not None
    source = Path(spec.origin).read_text(encoding="utf-8")

    assert 'commands=["ai-status"]' in source
    assert 'on_command("ai-status"' in source
    assert 'on_command("ai"' not in source
    assert "scene-level" not in source
