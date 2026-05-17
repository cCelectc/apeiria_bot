from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any

from apeiria.ai.tools import (
    AIToolDefinition,
    AIToolLevel,
    AIToolReadiness,
    AIToolResult,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

INTERNAL_TOOL_NAMES = (
    "future_task.cancel",
    "future_task.create",
    "future_task.list",
    "knowledge.search",
    "memory.search",
    "memory.write",
    "relationship.inspect",
)
EXPECTED_REGISTERED_TOOL_COUNT = len(INTERNAL_TOOL_NAMES) + 1


def _tool(name: str, *, origin: str = "plugin") -> AIToolDefinition:
    async def handler(**_: Any) -> AIToolResult:
        return AIToolResult(summary="ok")

    return AIToolDefinition(
        name=name,
        description=f"{name} description",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.READ,
        executor=handler,
        readiness=AIToolReadiness.available(),
        origin=origin,  # type: ignore[arg-type]
        manageable=origin == "plugin",
    )


class _FakeToolRegistry:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.tools: dict[str, AIToolDefinition] = {}

    def register(self, tool: AIToolDefinition) -> None:
        self._order.append(f"tool:{tool.name}")
        self.tools[tool.name] = tool

    def list_tools(self) -> list[AIToolDefinition]:
        return [self.tools[name] for name in sorted(self.tools)]


class _FakeToolService:
    def __init__(self, order: list[str]) -> None:
        self.registry = _FakeToolRegistry(order)


class _FakeSkillService:
    def __init__(self, order: list[str], tool_service: _FakeToolService) -> None:
        del tool_service
        self._order = order
        self.calls: list[tuple[Path, ...]] = []
        self.skill_sources: tuple[Path, ...] = ()

    def ensure_initialized(
        self,
        *,
        skill_sources: tuple[Path, ...] = (),
    ) -> None:
        self._order.append("skills")
        self.calls.append(skill_sources)
        self.skill_sources = skill_sources

    def list_skills(self) -> list[object]:
        from apeiria.ai.skills.contracts import build_file_skill_metadata
        from apeiria.ai.skills.loader import load_skills_from_sources

        return [
            build_file_skill_metadata(skill)
            for skill in load_skills_from_sources(self.skill_sources)
        ]


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
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    order: list[str] = []
    tool_service = _FakeToolService(order)
    skill_service = _FakeSkillService(order, tool_service)
    future_service = _FakeFutureTaskService(order)
    contributions = AIContributionRegistry()
    skill_dir = tmp_path / "plugin" / "skills"

    contributions.register_tool(tool=_tool("plugin.echo"))
    contributions.register_skill_source(skill_dir)

    def app_loader(registry: AIContributionRegistry) -> int:
        from apeiria.app.ai.builtin_tools import register_internal_tools

        order.append("app_loader")
        return register_internal_tools(registry)

    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=contributions,
        tool_service=tool_service,
        skill_service=skill_service,
        future_task_service=future_service,
        app_tool_loader=app_loader,
    )

    snapshot = asyncio.run(coordinator.startup())
    asyncio.run(coordinator.startup())

    first_startup_order = order[: order.index("future_recovery") + 1]
    assert first_startup_order[0] == "app_loader"
    assert first_startup_order[-2:] == ["skills", "future_recovery"]
    assert set(first_startup_order[1:-2]) == {
        *[f"tool:{name}" for name in INTERNAL_TOOL_NAMES],
        "tool:plugin.echo",
    }
    assert "builtin_catalog" not in order
    assert "pending_tools" not in order
    assert "plugin.echo" in tool_service.registry.tools
    assert tool_service.registry.tools["plugin.echo"].origin == "plugin"
    assert skill_service.calls[0] == (skill_dir.resolve(),)
    assert all(skill.name != "plugin.echo" for skill in skill_service.list_skills())
    assert not hasattr(snapshot, "capabilities")
    assert future_service.calls == 1
    assert len(tool_service.registry.tools) == EXPECTED_REGISTERED_TOOL_COUNT


def test_admin_fallback_initialization_does_not_recover_future_tasks() -> None:
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.app.ai.lifecycle import AIPluginLifecycleCoordinator

    order: list[str] = []
    tool_service = _FakeToolService(order)
    skill_service = _FakeSkillService(order, tool_service)
    future_service = _FakeFutureTaskService(order)

    coordinator = AIPluginLifecycleCoordinator(
        contribution_registry=AIContributionRegistry(),
        tool_service=tool_service,
        skill_service=skill_service,
        future_task_service=future_service,
    )

    snapshot = coordinator.ensure_runtime_support_initialized(source="admin_fallback")

    assert snapshot.initialized is True
    assert snapshot.initialization_source == "admin_fallback"
    assert "skills" in order
    assert "future_recovery" not in order
    assert future_service.calls == 0
    assert snapshot.recovery is None


def test_public_plugin_ai_tool_decorator_registers_plugin_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apeiria.ai.plugin_api as plugin_api_module
    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.ai.plugin_api import ai_tool

    registry = AIContributionRegistry()
    monkeypatch.setattr(plugin_api_module, "ai_contributions", registry)

    @ai_tool(
        name="plugin.echo",
        description="echo from a plugin",
        required_level="read",
    )
    async def echo_tool(message: str, *, context: object) -> AIToolResult:
        del message, context
        return AIToolResult(summary="ok")

    snapshot = registry.snapshot()

    assert echo_tool.__ai_tool_definition__.origin == "plugin"
    assert [tool.tool.name for tool in snapshot.tools] == ["plugin.echo"]
    assert snapshot.tools[0].tool.origin == "plugin"
    assert snapshot.tools[0].tool.required_level.value == "read"


def test_plugin_ai_tool_decorator_does_not_accept_origin_parameter() -> None:
    from apeiria.ai.plugin_api import ai_tool

    signature = inspect.signature(ai_tool)

    assert "origin" not in signature.parameters
    assert "tags" not in signature.parameters


def test_removed_plugin_tool_helper_is_not_exported() -> None:
    import apeiria.ai.plugin_api as plugin_api_module

    assert not hasattr(plugin_api_module, "register_ai_tool")


def test_contribution_registry_does_not_export_plugin_tool_api() -> None:
    import apeiria.ai.contributions as contribution_module

    assert not hasattr(contribution_module, "register_ai_tool")
    assert not hasattr(contribution_module, "ai_tool")
    assert hasattr(contribution_module, "register_ai_skill_source")


def test_contribution_registry_preserves_explicit_internal_origin() -> None:
    from apeiria.ai.contributions import AIContributionRegistry

    registry = AIContributionRegistry()
    contribution = registry.register_tool(
        tool=_tool("internal.echo", origin="internal")
    )

    assert contribution.tool.origin == "internal"
    assert registry.snapshot().tools[0].tool.origin == "internal"


def test_definition_ai_tool_decorator_declares_without_registration() -> None:
    from apeiria.ai.tools.decorators import ai_tool as define_ai_tool

    @define_ai_tool(
        name="internal.decorated",
        description="decorated internal tool",
        required_level=AIToolLevel.READ,
    )
    async def decorated_tool(*, context: object) -> AIToolResult:
        del context
        return AIToolResult(summary="ok")

    assert decorated_tool.__ai_tool_definition__.origin == "internal"
    assert decorated_tool.__ai_tool_definition__.name == "internal.decorated"


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
