"""Tests for user profile service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from apeiria.ai.profile.models import AIProfileUpdateInput
from apeiria.ai.profile.service import AIProfileService
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.anyio
async def test_ensure_and_get_profile(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        svc = AIProfileService()
        profile = await svc.ensure_profile(platform="qq", user_id="user123")
        assert profile.platform == "qq"
        assert profile.user_id == "user123"

        found = await svc.get_profile(platform="qq", user_id="user123")
        assert found is not None

        await svc.ensure_profile(platform="qq", user_id="u2")
        profiles = await svc.list_profiles(limit=50)
        assert len(profiles) >= 2  # noqa: PLR2004


@pytest.mark.anyio
async def test_update_profile_display_name(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        svc = AIProfileService()
        profile = await svc.ensure_profile(platform="qq", user_id="user123")
        updated = await svc.update_profile(
            profile_id=profile.profile_id,
            update_input=AIProfileUpdateInput(
                display_name="Alice", preferred_name="Ali"
            ),
        )
        assert updated is not None
        assert updated.display_name == "Alice"
        assert updated.preferred_name == "Ali"


@pytest.mark.anyio
async def test_ingest_message_self_introduction(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        svc = AIProfileService()
        await svc.ensure_profile(platform="qq", user_id="user123")
        result = await svc.ingest_message(
            platform="qq",
            user_id="user123",
            scene_type="private",
            self_introduction_name="Bob",
        )
        assert result is not None
        assert result.preferred_name == "Bob"
        assert result.name_source == "self_introduced"


@pytest.mark.anyio
async def test_delete_profile(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        svc = AIProfileService()
        profile = await svc.ensure_profile(platform="qq", user_id="user123")
        deleted = await svc.delete_profile(profile_id=profile.profile_id)
        assert deleted is True
        found = await svc.get_profile(platform="qq", user_id="user123")
        assert found is None
