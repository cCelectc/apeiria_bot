"""Tests for relationship service and scoring functions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from apeiria.ai.relationship.models import AIRelationshipDelta, AIRelationshipState
from apeiria.ai.relationship.scoring import (
    apply_relationship_delta,
    clamp_relationship_score,
    relationship_tier,
)
from apeiria.ai.relationship.service import AIRelationshipService
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


class TestScoringFunctions:
    def test_clamp_upper(self) -> None:
        assert clamp_relationship_score(150) == 100  # noqa: PLR2004

    def test_clamp_lower(self) -> None:
        assert clamp_relationship_score(-200) == -100  # noqa: PLR2004

    def test_clamp_passthrough(self) -> None:
        assert clamp_relationship_score(42) == 42  # noqa: PLR2004

    def test_tier_close(self) -> None:
        assert relationship_tier(65) == "close"

    def test_tier_warm(self) -> None:
        assert relationship_tier(30) == "warm"

    def test_tier_neutral(self) -> None:
        assert relationship_tier(0) == "neutral"
        assert relationship_tier(-15) == "neutral"

    def test_tier_cold(self) -> None:
        assert relationship_tier(-80) == "cold"

    def test_tier_guarded(self) -> None:
        assert relationship_tier(-45) == "guarded"

    def test_apply_delta_updates_score_and_mood(self) -> None:
        now = datetime.now(timezone.utc)
        state = AIRelationshipState(
            affinity_id="a1",
            platform="qq",
            user_id="u1",
            score=10,
            mood_tags=(),
            last_event_at=now,
            last_decay_at=None,
        )
        delta = AIRelationshipDelta(
            score_delta=5,
            mood_tag="playful_contact",
            event_type="message",
        )
        updated = apply_relationship_delta(state, delta)
        assert updated.score == 15  # noqa: PLR2004
        assert "playful_contact" in updated.mood_tags

    def test_apply_delta_clamps_score(self) -> None:
        now = datetime.now(timezone.utc)
        state = AIRelationshipState(
            affinity_id="a1",
            platform="qq",
            user_id="u1",
            score=99,
            mood_tags=(),
            last_event_at=now,
            last_decay_at=None,
        )
        delta = AIRelationshipDelta(score_delta=5, event_type="message")
        updated = apply_relationship_delta(state, delta)
        assert updated.score == 100  # noqa: PLR2004


class TestRelationshipService:
    @pytest.mark.anyio
    async def test_apply_delta_and_get_state(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = AIRelationshipService()
            state = await svc.apply_delta(
                platform="qq",
                user_id="user123",
                scene_id="scene1",
                delta=AIRelationshipDelta(
                    score_delta=3,
                    mood_tag="positive_contact",
                    event_type="message",
                    reason="friendly message",
                ),
            )
            assert state.platform == "qq"
            assert state.user_id == "user123"
            assert state.score == 3  # noqa: PLR2004
            assert "positive_contact" in state.mood_tags

            loaded = await svc.get_state(platform="qq", user_id="user123")
            assert loaded.score == 3  # noqa: PLR2004

    @pytest.mark.anyio
    async def test_project_state(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = AIRelationshipService()
            proj = await svc.project_state(platform="qq", user_id="user_new")
            assert proj.tone in ("neutral", "cold", "guarded", "warm", "close")

    @pytest.mark.anyio
    async def test_multiple_deltas_accumulate(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = AIRelationshipService()
            await svc.apply_delta(
                platform="qq",
                user_id="u1",
                scene_id="s1",
                delta=AIRelationshipDelta(score_delta=4, event_type="message"),
            )
            await svc.apply_delta(
                platform="qq",
                user_id="u1",
                scene_id="s2",
                delta=AIRelationshipDelta(score_delta=2, event_type="message"),
            )
            state = await svc.get_state(platform="qq", user_id="u1")
            assert state.score == 6  # noqa: PLR2004

    @pytest.mark.anyio
    async def test_list_states(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = AIRelationshipService()
            await svc.apply_delta(
                platform="qq",
                user_id="u1",
                scene_id=None,
                delta=AIRelationshipDelta(score_delta=1, event_type="message"),
            )
            await svc.apply_delta(
                platform="qq",
                user_id="u2",
                scene_id=None,
                delta=AIRelationshipDelta(score_delta=2, event_type="message"),
            )
            states = await svc.list_states(limit=10)
            assert len(states) == 2  # noqa: PLR2004
