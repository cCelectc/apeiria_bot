from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from apeiria.ai.contributions import AIContributionRegistry
from apeiria.ai.plugin_api import ai_skill_source, live_platform_context
from apeiria.bot.live_context import live_platform_context as set_live_platform_context

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_plugin_api_ai_skill_source_resolves_explicit_base_path(
    monkeypatch: MonkeyPatch,
) -> None:
    registry = AIContributionRegistry()
    monkeypatch.setattr("apeiria.ai.plugin_api.ai_contributions", registry)
    base_path = Path(__file__).parent

    resolved = ai_skill_source("skills/example/SKILL.md", base_path=base_path)

    assert resolved == (base_path / "skills/example/SKILL.md").resolve(strict=False)
    assert registry.snapshot().skill_sources[0].path == resolved


def test_plugin_api_ai_skill_source_resolves_from_caller_module(
    monkeypatch: MonkeyPatch,
) -> None:
    registry = AIContributionRegistry()
    monkeypatch.setattr("apeiria.ai.plugin_api.ai_contributions", registry)

    resolved = _register_relative_skill_source()

    assert resolved == (Path(__file__).parent / "local/SKILL.md").resolve(strict=False)
    assert registry.snapshot().skill_sources[0].path == resolved


def test_plugin_api_live_platform_context_reads_current_turn() -> None:
    bot = _FakeBot()
    event = _FakeEvent()

    assert live_platform_context() is None
    with set_live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
        live = live_platform_context()
        assert live is not None
        assert live.bot is bot
        assert live.event is event
    assert live_platform_context() is None


def _register_relative_skill_source() -> Path:
    return ai_skill_source("local/SKILL.md")


class _FakeBot:
    pass


class _FakeEvent:
    pass
