from __future__ import annotations

import asyncio
import importlib
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from apeiria.ai.relationship.repository import datetime_to_text
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

MAX_SCORE = 100
CLOSE_SCORE = 61
NEUTRAL_EDGE_SCORE = 20
GUARDED_EDGE_SCORE = -21
POST_NEGATIVE_SCORE = 97
REPEATED_PRAISE_SCORE = 2


def test_profile_and_relationship_boundaries_use_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory.contracts import AIMemoryCreateInput
    from apeiria.ai.memory.service import ai_memory_service
    from apeiria.ai.profile.service import ai_profile_service
    from apeiria.ai.relationship.models import AIRelationshipDelta
    from apeiria.ai.relationship.scoring import relationship_tier
    from apeiria.ai.relationship.service import ai_relationship_service

    async def scenario() -> None:
        profile = await ai_profile_service.ingest_message(
            platform="onebot",
            user_id="user-1",
            scene_type="private",
            self_introduction_name="Mika",
        )

        assert profile is not None
        assert profile.preferred_name == "Mika"
        assert profile.name_visibility == "private_only"

        memory = await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="preference",
                content="likes concise technical answers",
                salience=0.8,
                confidence=0.9,
            )
        )

        private_card = await ai_profile_service.build_profile_card(
            platform="onebot",
            user_id="user-1",
            scene_type="private",
            memories=(memory,),
        )
        group_card = await ai_profile_service.build_profile_card(
            platform="onebot",
            user_id="user-1",
            scene_type="group",
            memories=(memory,),
        )

        assert private_card is not None
        assert "- 首选名称: Mika" in private_card.lines
        assert memory.memory_id in private_card.source_refs
        assert group_card is not None
        assert "- 首选名称: Mika" not in group_card.lines
        assert not hasattr(profile, "memory_points")
        assert not hasattr(profile, "relationship_score")

        state = await ai_relationship_service.set_manual_score(
            platform="onebot",
            user_id="user-1",
            score=120,
            scene_id="group-1",
        )
        assert state.score == MAX_SCORE
        assert relationship_tier(CLOSE_SCORE) == "close"
        assert relationship_tier(NEUTRAL_EDGE_SCORE) == "neutral"
        assert relationship_tier(GUARDED_EDGE_SCORE) == "guarded"

        shared = await ai_relationship_service.apply_delta(
            platform="onebot",
            user_id="user-1",
            scene_id="private:user-1",
            delta=AIRelationshipDelta(
                score_delta=-3,
                mood_tag="negative_contact",
                reason="direct negative interaction",
            ),
        )
        assert shared.affinity_id == state.affinity_id
        assert shared.score == POST_NEGATIVE_SCORE

        events = await ai_relationship_service.list_events_for_target(
            platform="onebot",
            user_id="user-1",
            limit=10,
        )
        assert {event.scene_id for event in events} >= {"group-1", "private:user-1"}
        assert {event.event_type for event in events} >= {"manual", "message"}

        await _assert_repeated_praise_uses_recent_window(
            relationship_service=ai_relationship_service,
            delta_type=AIRelationshipDelta,
        )

        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT last_event_at, last_decay_at
                FROM ai_affinity
                WHERE affinity_id = ?
                """,
                (shared.affinity_id,),
            ).fetchone()
            assert row is not None
            last_event_at = state.last_event_at - timedelta(days=30)
            connection.execute(
                """
                UPDATE ai_affinity
                SET last_event_at = ?, last_decay_at = ?
                WHERE affinity_id = ?
                """,
                (datetime_to_text(last_event_at), None, shared.affinity_id),
            )

        decayed = await ai_relationship_service.apply_delta(
            platform="onebot",
            user_id="user-1",
            scene_id="private:user-1",
            delta=AIRelationshipDelta(score_delta=-1, reason="direct correction"),
        )
        assert 0 < decayed.score < shared.score
        decay_events = await ai_relationship_service.list_events_for_target(
            platform="onebot",
            user_id="user-1",
            limit=10,
        )
        decay_event = next(
            event for event in decay_events if event.event_type == "decay"
        )
        assert decay_event.mood_tag is None

    asyncio.run(scenario())


async def _assert_repeated_praise_uses_recent_window(
    *,
    relationship_service: Any,
    delta_type: Any,
) -> None:
    ambient_delta = delta_type(
        score_delta=1,
        mood_tag="positive_contact",
        reason="direct positive interaction",
    )
    for index in range(3):
        await relationship_service.apply_delta(
            platform="onebot",
            user_id="user-2",
            scene_id=f"group-{index}",
            delta=ambient_delta,
        )
    repeated = await relationship_service.get_state(
        platform="onebot",
        user_id="user-2",
    )
    assert repeated.score == REPEATED_PRAISE_SCORE

    with database_runtime.connect_sync() as connection:
        past_event_at = repeated.last_event_at - timedelta(days=2)
        connection.execute(
            """
            UPDATE ai_relationship_event
            SET created_at = ?
            WHERE affinity_id = ?
            """,
            (datetime_to_text(past_event_at), repeated.affinity_id),
        )

    renewed = await relationship_service.apply_delta(
        platform="onebot",
        user_id="user-2",
        scene_id="private:user-2",
        delta=ambient_delta,
    )
    assert renewed.score == REPEATED_PRAISE_SCORE + 1


def test_legacy_person_profile_public_surfaces_are_removed() -> None:
    assert importlib.util.find_spec("apeiria.ai.person") is None

    from apeiria.ai.prompting.reply import ReplyPromptInput

    assert "profile_card" in ReplyPromptInput.__dataclass_fields__
    assert "person_profile" not in ReplyPromptInput.__dataclass_fields__
