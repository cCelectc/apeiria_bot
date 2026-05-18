from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_TOOL_TIMEOUT_SECONDS = 8.0
DEFAULT_CONVERSATION_RETENTION_DAYS = 30
UPDATED_AMBIENT_MERGE_WINDOW_MS = 250
UPDATED_TOOL_TIMEOUT_SECONDS = 3.5


def test_ai_runtime_settings_defaults_without_saved_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    view = AIRuntimeSettingsService().get_view()

    assert view.effective.allow_group_initiative is False
    assert view.effective.direct_bypass_ambient_budget is True
    assert view.effective.tool_execution_timeout_seconds == DEFAULT_TOOL_TIMEOUT_SECONDS
    assert view.defaults == view.effective
    assert view.overrides == {}
    assert view.updated_at is None


def test_ai_runtime_settings_persist_across_service_recreation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    first = AIRuntimeSettingsService()
    updated = first.update_settings(
        {
            "allow_group_initiative": True,
            "ambient_merge_window_ms": UPDATED_AMBIENT_MERGE_WINDOW_MS,
            "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS,
        }
    )

    reloaded = AIRuntimeSettingsService().get_view()

    assert updated.effective.allow_group_initiative is True
    assert reloaded.effective.allow_group_initiative is True
    assert reloaded.effective.ambient_merge_window_ms == UPDATED_AMBIENT_MERGE_WINDOW_MS
    assert (
        reloaded.effective.tool_execution_timeout_seconds
        == UPDATED_TOOL_TIMEOUT_SECONDS
    )
    assert reloaded.defaults.allow_group_initiative is False
    assert reloaded.overrides == {
        "allow_group_initiative": True,
        "ambient_merge_window_ms": UPDATED_AMBIENT_MERGE_WINDOW_MS,
        "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS,
    }
    assert reloaded.updated_at is not None


def test_ai_runtime_settings_can_clear_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    service = AIRuntimeSettingsService()
    service.update_settings({"allow_group_initiative": True})
    cleared = service.update_settings({}, clear=["allow_group_initiative"])

    assert cleared.effective.allow_group_initiative is False
    assert cleared.overrides == {}


def test_ai_runtime_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    service = AIRuntimeSettingsService()

    with pytest.raises(ValidationError):
        service.update_settings({"tool_execution_timeout_seconds": -1})

    with pytest.raises(ValidationError):
        service.update_settings({"conversation_retention_days": 0})

    with pytest.raises(ValidationError):
        service.update_settings({"allow_group_initiative": "yes"})

    assert service.get_view().overrides == {}


def test_legacy_plugin_ai_config_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    (tmp_path / "apeiria.config.toml").write_text(
        """
[plugins.ai]
allow_group_initiative = true
tool_execution_timeout_seconds = 1.5
conversation_retention_days = 2
""",
        encoding="utf-8",
    )
    database_runtime.ensure_ready()

    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    view = AIRuntimeSettingsService().get_view()

    assert view.effective.allow_group_initiative is False
    assert view.effective.tool_execution_timeout_seconds == DEFAULT_TOOL_TIMEOUT_SECONDS
    assert (
        view.effective.conversation_retention_days
        == DEFAULT_CONVERSATION_RETENTION_DAYS
    )
    assert view.overrides == {}
