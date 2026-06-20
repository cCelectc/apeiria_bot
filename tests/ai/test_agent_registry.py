from __future__ import annotations

import time

from apeiria.ai.agent.registry import AgentRegistry, _AgentEntry


class _FakeAgent:
    is_streaming = False


def test_agent_registry_get_or_create() -> None:
    registry = AgentRegistry()
    factory_called = 0

    def factory(_sid: str) -> _FakeAgent:  # type: ignore[return-value]
        nonlocal factory_called
        factory_called += 1
        return _FakeAgent()

    agent1 = registry.get_or_create("s1", factory)
    assert factory_called == 1
    agent2 = registry.get_or_create("s1", factory)
    assert factory_called == 1
    assert agent1 is agent2


def test_agent_registry_different_sessions() -> None:
    registry = AgentRegistry()

    def factory(_sid: str) -> _FakeAgent:  # type: ignore[return-value]
        return _FakeAgent()

    a1 = registry.get_or_create("s1", factory)
    a2 = registry.get_or_create("s2", factory)
    assert a1 is not a2
    assert registry.active_count == 2  # noqa: PLR2004


def test_agent_registry_sweep() -> None:
    registry = AgentRegistry()
    registry._agents["old"] = _AgentEntry(
        agent=_FakeAgent(),  # type: ignore[arg-type]
        last_access=time.monotonic() - 90000,
    )
    registry._agents["new"] = _AgentEntry(
        agent=_FakeAgent(),  # type: ignore[arg-type]
        last_access=time.monotonic(),
    )
    swept = registry.sweep_expired()
    assert swept == 1
    assert "old" not in registry._agents
    assert "new" in registry._agents


def test_agent_registry_remove() -> None:
    registry = AgentRegistry()

    def factory(_sid: str) -> _FakeAgent:  # type: ignore[return-value]
        return _FakeAgent()

    registry.get_or_create("s1", factory)
    assert registry.active_count == 1
    registry.remove("s1")
    assert registry.active_count == 0


def test_agent_registry_sweep_skips_streaming() -> None:
    registry = AgentRegistry()

    class _StreamingAgent:
        is_streaming = True

    registry._agents["streaming"] = _AgentEntry(
        agent=_StreamingAgent(),  # type: ignore[arg-type]
        last_access=time.monotonic() - 90000,
    )
    swept = registry.sweep_expired()
    assert swept == 0
    assert "streaming" in registry._agents
