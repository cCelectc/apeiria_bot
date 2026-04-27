"""Person profile storage and prompt-building service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.memory.extraction import select_person_profile_candidates
from apeiria.ai.person.models import (
    AIPersonMemoryPoint,
    AIPersonMemoryPointCategory,
    AIPersonProfileDefinition,
    AIPersonPromptProfile,
)
from apeiria.ai.person.repository import (
    PersonProfileRepository,
    PersonProfileRow,
    utcnow,
)
from apeiria.ai.relationship.service import ai_relationship_service

if TYPE_CHECKING:
    from apeiria.ai.memory.models import AIMemoryExtractionCandidate

_MAX_STORED_MEMORY_POINTS = 12
_MAX_PROMPT_POINTS_PER_CATEGORY = 2
_CANDIDATE_MIN_CONFIDENCE = 0.6
_PROMPT_CATEGORY_LABELS: dict[AIPersonMemoryPointCategory, str] = {
    "preference": "Stable preference",
    "fact": "Stable fact",
    "relationship": "Relationship clue",
    "impression": "Impression point",
}


@dataclass(frozen=True)
class _ProfileDraft:
    preferred_name: str | None
    name_reason: str | None
    memory_points: tuple[AIPersonMemoryPoint, ...]


class AIPersonProfileService:
    """Persistence and prompt assembly for known-user profiles."""

    def __init__(
        self,
        *,
        repository: PersonProfileRepository | None = None,
    ) -> None:
        self._repository = repository or PersonProfileRepository()

    async def get_profile_by_id(
        self,
        *,
        person_id: str,
    ) -> AIPersonProfileDefinition | None:
        row = self._repository.get_profile_row_by_id(person_id=person_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def get_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> AIPersonProfileDefinition | None:
        row = self._repository.get_profile_row(platform=platform, user_id=user_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def ensure_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> PersonProfileRow:
        return self._repository.ensure_profile(platform=platform, user_id=user_id)

    async def list_profiles(
        self,
        *,
        limit: int = 50,
    ) -> list[AIPersonProfileDefinition]:
        return [
            self._to_definition(row)
            for row in self._repository.list_profile_rows(limit=limit)
        ]

    async def update_profile(
        self,
        *,
        person_id: str,
        person_name: str | None = None,
        nickname: str | None = None,
        memory_points: tuple[AIPersonMemoryPoint, ...] | None = None,
    ) -> AIPersonProfileDefinition | None:
        row = self._repository.get_profile_row_by_id(person_id=person_id)
        if row is None:
            return None
        if person_name is not None:
            row.person_name = person_name or None
        if nickname is not None:
            row.nickname = nickname or None
        if memory_points is not None:
            row.memory_points_json = self._serialize_memory_points(memory_points)
        row.updated_at = utcnow()
        self._repository.update_profile_row(row)
        return self._to_definition(row)

    async def delete_profile(
        self,
        *,
        person_id: str,
    ) -> bool:
        return self._repository.delete_profile(person_id=person_id)

    async def ingest_message(
        self,
        *,
        platform: str,
        user_id: str,
        source_message_id: str | None,
        candidates: tuple["AIMemoryExtractionCandidate", ...] = (),
        self_introduction_name: str | None = None,
    ) -> AIPersonProfileDefinition | None:
        draft = _build_profile_draft(
            source_message_id=source_message_id,
            candidates=candidates,
            self_introduction_name=self_introduction_name,
        )
        has_profile_signal = _has_profile_signal(draft)
        row = self._repository.get_profile_row(
            platform=platform,
            user_id=user_id,
        )
        if row is None and not has_profile_signal:
            return None
        if row is None:
            row = await self.ensure_profile(
                platform=platform,
                user_id=user_id,
            )

        now = utcnow()
        row.last_interaction = now
        row.updated_at = now
        if not has_profile_signal:
            self._repository.update_profile_row(row)
            return self._to_definition(row)

        row.is_known = True
        row.know_since = row.know_since or now
        existing_points = self._deserialize_memory_points(row.memory_points_json)
        if draft.preferred_name:
            row.nickname = draft.preferred_name
            row.person_name = row.person_name or draft.preferred_name
            row.name_reason = draft.name_reason
        row.memory_points_json = self._serialize_memory_points(
            _merge_memory_points(existing_points, draft.memory_points)
        )
        self._repository.update_profile_row(row)
        return self._to_definition(row)

    async def build_prompt_profile(
        self,
        *,
        platform: str,
        user_id: str,
        group_id: str | None,
    ) -> AIPersonPromptProfile | None:
        profile = await self.get_profile(
            platform=platform,
            user_id=user_id,
        )
        if profile is None:
            return None

        preferred_name = profile.nickname or profile.person_name
        prompt_points = _select_prompt_points(profile.memory_points)
        if not preferred_name and not prompt_points:
            return None

        (
            relationship_score,
            mood_tags,
        ) = await ai_relationship_service.get_state_snapshot(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        lines: list[str] = []
        if preferred_name:
            lines.append(f"- Preferred name: {preferred_name}")
        if profile.know_since is not None:
            lines.append(f"- Known since: {profile.know_since.date().isoformat()}")
        for point in prompt_points:
            label = _PROMPT_CATEGORY_LABELS.get(point.category, "Profile point")
            lines.append(f"- {label}: {point.content}")
        if lines:
            mood_text = ", ".join(mood_tags) if mood_tags else "none"
            lines.append(
                "- Relationship snapshot: "
                f"affinity={relationship_score:.2f}; mood_tags={mood_text}"
            )
        return AIPersonPromptProfile(
            person_id=profile.person_id,
            preferred_name=preferred_name,
            prompt_lines=tuple(lines),
            relationship_score=relationship_score,
            mood_tags=mood_tags,
        )

    @staticmethod
    def _serialize_memory_points(points: tuple[AIPersonMemoryPoint, ...]) -> str:
        payload = [
            {
                "category": point.category,
                "content": point.content,
                "confidence": point.confidence,
                "source_message_id": point.source_message_id,
            }
            for point in points
        ]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _deserialize_memory_points(
        raw_json: str | None,
    ) -> tuple[AIPersonMemoryPoint, ...]:
        if not raw_json:
            return ()
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            return ()
        if not isinstance(parsed, list):
            return ()
        points: list[AIPersonMemoryPoint] = []
        for row in parsed:
            if not isinstance(row, dict):
                continue
            category = row.get("category")
            content = row.get("content")
            confidence = row.get("confidence")
            if category not in _PROMPT_CATEGORY_LABELS:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            if not isinstance(confidence, (int, float)):
                continue
            source_message_id = row.get("source_message_id")
            points.append(
                AIPersonMemoryPoint(
                    category=category,
                    content=content.strip(),
                    confidence=max(0.0, min(1.0, float(confidence))),
                    source_message_id=(
                        source_message_id.strip()
                        if isinstance(source_message_id, str)
                        and source_message_id.strip()
                        else None
                    ),
                )
            )
        return tuple(points)

    def _to_definition(self, row: PersonProfileRow) -> AIPersonProfileDefinition:
        return AIPersonProfileDefinition(
            person_id=row.person_id,
            platform=row.platform,
            user_id=row.user_id,
            person_name=row.person_name,
            nickname=row.nickname,
            name_reason=row.name_reason,
            memory_points=self._deserialize_memory_points(row.memory_points_json),
            is_known=row.is_known,
            know_since=row.know_since,
            last_interaction=row.last_interaction,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _build_profile_draft(
    *,
    source_message_id: str | None,
    candidates: tuple["AIMemoryExtractionCandidate", ...],
    self_introduction_name: str | None,
) -> _ProfileDraft:
    points: list[AIPersonMemoryPoint] = []
    for candidate in select_person_profile_candidates(list(candidates)):
        point = _candidate_to_memory_point(candidate, source_message_id)
        if point is not None:
            points.append(point)
    return _ProfileDraft(
        preferred_name=self_introduction_name,
        name_reason="self_introduced" if self_introduction_name else None,
        memory_points=tuple(points),
    )


def _has_profile_signal(draft: _ProfileDraft) -> bool:
    return bool(draft.preferred_name or draft.memory_points)


def _candidate_to_memory_point(
    candidate: "AIMemoryExtractionCandidate",
    source_message_id: str | None,
) -> AIPersonMemoryPoint | None:
    if candidate.confidence < _CANDIDATE_MIN_CONFIDENCE:
        return None
    category_map: dict[str, AIPersonMemoryPointCategory] = {
        "preference": "preference",
        "fact": "fact",
        "relationship": "relationship",
        "impression": "impression",
    }
    category = category_map.get(candidate.memory_kind)
    if category is None:
        return None
    return AIPersonMemoryPoint(
        category=category,
        content=candidate.content,
        confidence=candidate.confidence,
        source_message_id=source_message_id,
    )


def _merge_memory_points(
    existing_points: tuple[AIPersonMemoryPoint, ...],
    new_points: tuple[AIPersonMemoryPoint, ...],
) -> tuple[AIPersonMemoryPoint, ...]:
    merged: dict[tuple[str, str], AIPersonMemoryPoint] = {
        (point.category, point.content): point for point in existing_points
    }
    for point in new_points:
        key = (point.category, point.content)
        current = merged.get(key)
        if current is None or point.confidence >= current.confidence:
            merged[key] = point
    ordered = sorted(
        merged.values(),
        key=lambda item: (item.confidence, item.category, item.content),
        reverse=True,
    )
    return tuple(ordered[:_MAX_STORED_MEMORY_POINTS])


def _select_prompt_points(
    memory_points: tuple[AIPersonMemoryPoint, ...],
) -> tuple[AIPersonMemoryPoint, ...]:
    selected: list[AIPersonMemoryPoint] = []
    counts: dict[AIPersonMemoryPointCategory, int] = {}
    for point in sorted(memory_points, key=lambda item: item.confidence, reverse=True):
        if counts.get(point.category, 0) >= _MAX_PROMPT_POINTS_PER_CATEGORY:
            continue
        selected.append(point)
        counts[point.category] = counts.get(point.category, 0) + 1
    return tuple(selected)


ai_person_profile_service = AIPersonProfileService()
