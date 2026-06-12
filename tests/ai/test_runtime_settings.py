from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_TOOL_TIMEOUT_SECONDS = 8.0
DEFAULT_DUPLICATE_EVENT_TTL_SECONDS = 30
DEFAULT_QUIET_HOURS_END_MINUTE = 420
UPDATED_QUIET_HOURS_START_MINUTE = 30
UPDATED_QUIET_HOURS_END_MINUTE = 390
UPDATED_NIGHT_AWAKE_LEASE_MINUTES = 7
UPDATED_AMBIENT_MERGE_WINDOW_MS = 250
UPDATED_DUPLICATE_EVENT_TTL_SECONDS = 45
UPDATED_TOOL_TIMEOUT_SECONDS = 3.5


def test_ai_runtime_settings_defaults_without_saved_row(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            view = await AIRuntimeSettingsService().get_view()

            assert view.effective.allow_group_initiative is False
            assert view.effective.quiet_hours_enabled is False
            assert (
                view.effective.quiet_hours_end_minute == DEFAULT_QUIET_HOURS_END_MINUTE
            )
            assert view.overrides == {}
            assert view.updated_at is None

    asyncio.run(run())


def test_ai_runtime_settings_metadata_classifies_operator_visibility(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            fields = {
                field.key: field
                for field in (await AIRuntimeSettingsService().get_view()).fields
            }

            assert fields["allow_group_initiative"].visibility == "default"
            assert fields["quiet_hours_enabled"].visibility == "default"
            assert fields["quiet_hours_start_minute"].visibility == "advanced"
            assert fields["night_awake_lease_minutes"].visibility == "advanced"

    asyncio.run(run())


def test_ai_runtime_settings_persist_across_service_recreation(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            first = AIRuntimeSettingsService()
            updated = await first.update_settings(
                {
                    "allow_group_initiative": True,
                    "quiet_hours_enabled": True,
                    "quiet_hours_start_minute": UPDATED_QUIET_HOURS_START_MINUTE,
                    "quiet_hours_end_minute": UPDATED_QUIET_HOURS_END_MINUTE,
                    "night_awake_lease_minutes": UPDATED_NIGHT_AWAKE_LEASE_MINUTES,
                    "ambient_merge_window_ms": UPDATED_AMBIENT_MERGE_WINDOW_MS,
                    "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS,
                }
            )

            reloaded = await AIRuntimeSettingsService().get_view()

            assert updated.effective.allow_group_initiative is True
            assert updated.effective.quiet_hours_enabled is True
            assert reloaded.effective.allow_group_initiative is True
            assert reloaded.overrides == {
                "allow_group_initiative": True,
                "quiet_hours_enabled": True,
                "quiet_hours_start_minute": UPDATED_QUIET_HOURS_START_MINUTE,
                "quiet_hours_end_minute": UPDATED_QUIET_HOURS_END_MINUTE,
                "night_awake_lease_minutes": UPDATED_NIGHT_AWAKE_LEASE_MINUTES,
                "ambient_merge_window_ms": UPDATED_AMBIENT_MERGE_WINDOW_MS,
                "tool_execution_timeout_seconds": UPDATED_TOOL_TIMEOUT_SECONDS,
            }
            assert reloaded.updated_at is not None

    asyncio.run(run())


def test_ai_runtime_settings_can_clear_override(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            service = AIRuntimeSettingsService()
            await service.update_settings({"allow_group_initiative": True})
            cleared = await service.update_settings(
                {}, clear=["allow_group_initiative"]
            )

            assert cleared.effective.allow_group_initiative is False
            assert cleared.overrides == {}

    asyncio.run(run())


def test_hidden_ai_runtime_settings_still_persist_and_apply(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            service = AIRuntimeSettingsService()
            updated = await service.update_settings(
                {"duplicate_event_ttl_seconds": UPDATED_DUPLICATE_EVENT_TTL_SECONDS}
            )

            assert updated.overrides == {
                "duplicate_event_ttl_seconds": UPDATED_DUPLICATE_EVENT_TTL_SECONDS,
            }

            cleared = await service.update_settings(
                {}, clear=["duplicate_event_ttl_seconds"]
            )

            assert (
                cleared.effective.duplicate_event_ttl_seconds
                == DEFAULT_DUPLICATE_EVENT_TTL_SECONDS
            )

    asyncio.run(run())


def test_ai_runtime_settings_reject_invalid_values(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            service = AIRuntimeSettingsService()

            with pytest.raises(ValidationError):
                await service.update_settings({"tool_execution_timeout_seconds": -1})

            with pytest.raises(ValidationError):
                await service.update_settings({"conversation_retention_days": 0})

            with pytest.raises(ValidationError):
                await service.update_settings({"allow_group_initiative": "yes"})

            with pytest.raises(ValidationError):
                await service.update_settings({"quiet_hours_start_minute": 1440})

            with pytest.raises(ValidationError):
                await service.update_settings({"night_awake_lease_minutes": 0})

            assert (await service.get_view()).overrides == {}

    asyncio.run(run())


def test_legacy_plugin_ai_config_is_ignored(
    tmp_path: Path,
) -> None:
    from apeiria.ai.runtime_settings import AIRuntimeSettingsService

    (tmp_path / "apeiria.config.toml").write_text(
        """
[plugins.ai]
allow_group_initiative = true
tool_execution_timeout_seconds = 1.5
conversation_retention_days = 2
""",
        encoding="utf-8",
    )

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            view = await AIRuntimeSettingsService().get_view()

            assert view.effective.allow_group_initiative is False
            assert view.overrides == {}

    asyncio.run(run())
