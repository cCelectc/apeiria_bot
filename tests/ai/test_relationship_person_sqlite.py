from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

MANUAL_SCORE = 0.42


def test_relationship_and_person_profile_use_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory.models import AIMemoryExtractionCandidate
    from apeiria.ai.person.service import ai_person_profile_service
    from apeiria.ai.relationship.service import ai_relationship_service

    async def scenario() -> None:
        profile = await ai_person_profile_service.ingest_message(
            platform="onebot",
            user_id="user-1",
            source_message_id="msg-1",
            candidates=(
                AIMemoryExtractionCandidate(
                    memory_kind="preference",
                    content="likes concise technical answers",
                    confidence=0.9,
                    salience=0.8,
                ),
            ),
            self_introduction_name="Mika",
        )

        assert profile is not None
        assert profile.person_name == "Mika"
        assert profile.nickname == "Mika"
        assert profile.is_known is True
        assert profile.memory_points[0].content == "likes concise technical answers"

        state = await ai_relationship_service.set_manual_score(
            platform="onebot",
            group_id="group-1",
            user_id="user-1",
            score=MANUAL_SCORE,
        )
        assert state.score == MANUAL_SCORE

        prompt_profile = await ai_person_profile_service.build_prompt_profile(
            platform="onebot",
            group_id="group-1",
            user_id="user-1",
        )
        assert prompt_profile is not None
        assert prompt_profile.relationship_score == MANUAL_SCORE
        assert any(
            "Preferred name: Mika" in line for line in prompt_profile.prompt_lines
        )

        listed = await ai_relationship_service.list_states(limit=10)
        assert [item.affinity_id for item in listed] == [state.affinity_id]

        events = await ai_relationship_service.list_events_for_target(
            platform="onebot",
            group_id="group-1",
            user_id="user-1",
            limit=10,
        )
        assert len(events) == 1
        assert events[0].event_type == "manual"

    asyncio.run(scenario())
