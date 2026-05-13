from __future__ import annotations

import asyncio
from types import SimpleNamespace
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

EXPECTED_REGISTERED_TOOL_COUNT = 2


def _tool(name: str) -> AIToolDefinition:
    async def handler(**_: Any) -> AIToolResult:
        return AIToolResult(summary="ok")

    return AIToolDefinition(
        name=name,
        description=f"{name} description",
        input_schema={"type": "object", "properties": {}},
        required_level=AIToolLevel.READ,
        executor=handler,
        readiness=AIToolReadiness.available(),
        origin="plugin",
        manageable=True,
    )


class _FakeToolRegistry:
    def __init__(self, order: list[str]) -> None:
        self._order = order
        self.tools: dict[str, AIToolDefinition] = {}
        self.pending_tools = [_tool("app.future")]

    def register(self, tool: AIToolDefinition) -> None:
        self._order.append(f"tool:{tool.name}")
        self.tools[tool.name] = tool

    def list_tools(self) -> list[AIToolDefinition]:
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


class _FakeToolService:
    def __init__(self, order: list[str]) -> None:
        self.registry = _FakeToolRegistry(order)


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

    contributions.register_tool(tool=_tool("plugin.echo"))
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
        "skills",
        "future_recovery",
    ]
    assert "plugin.echo" in tool_service.registry.tools
    assert tool_service.registry.tools["plugin.echo"].origin == "plugin"
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
        register_ai_skill_source,
        register_ai_tool,
    )

    registry = AIPluginContributionRegistry()
    monkeypatch.setattr(contribution_module, "ai_plugin_contributions", registry)

    @register_ai_tool(
        name="plugin.echo",
        description="echo from a plugin",
        required_level="read",
    )
    async def echo_tool(message: str, *, context: object) -> AIToolResult:
        del message, context
        return AIToolResult(summary="ok")

    plugin_dir = tmp_path / "plugin"
    skill_source = register_ai_skill_source("skills", base_path=plugin_dir)
    snapshot = registry.snapshot()

    assert echo_tool.__ai_tool_definition__.origin == "plugin"
    assert [tool.tool.name for tool in snapshot.tools] == ["plugin.echo"]
    assert snapshot.tools[0].tool.origin == "plugin"
    assert snapshot.tools[0].tool.required_level.value == "read"
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
