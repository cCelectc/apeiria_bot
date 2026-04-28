# ruff: noqa: PLR2004

from __future__ import annotations

from apeiria.ai.config import AIPluginConfig


def test_ai_plugin_config_exposes_session_runtime_defaults() -> None:
    config = AIPluginConfig()

    assert config.ambient_merge_window_ms == 1500
    assert config.max_pending_messages == 12
    assert config.group_reply_cooldown_seconds == 180
    assert config.max_consecutive_ambient_replies == 1
    assert config.direct_bypass_ambient_budget is True
    assert config.duplicate_event_ttl_seconds == 30


def test_ai_plugin_config_accepts_session_runtime_overrides() -> None:
    config = AIPluginConfig(
        ambient_merge_window_ms=400,
        max_pending_messages=4,
        group_reply_cooldown_seconds=20,
        max_consecutive_ambient_replies=2,
        direct_bypass_ambient_budget=False,
        duplicate_event_ttl_seconds=5,
    )

    assert config.ambient_merge_window_ms == 400
    assert config.max_pending_messages == 4
    assert config.group_reply_cooldown_seconds == 20
    assert config.max_consecutive_ambient_replies == 2
    assert config.direct_bypass_ambient_budget is False
    assert config.duplicate_event_ttl_seconds == 5
