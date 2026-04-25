"""Person profile storage and prompt-building service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from apeiria.ai.memory.extraction import select_person_profile_candidates
from apeiria.ai.person.models import (
    AIPersonMemoryPoint,
    AIPersonMemoryPointCategory,
    AIPersonProfileDefinition,
    AIPersonPromptProfile,
)
from apeiria.ai.relationship.service import ai_relationship_service
from apeiria.db.runtime import database_runtime

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


@dataclass
class _PersonProfileRow:
    id: int
    person_id: str
    platform: str
    user_id: str
    person_name: str | None
    nickname: str | None
    name_reason: str | None
    memory_points_json: str
    is_known: bool
    know_since: datetime | None
    last_interaction: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class _ProfileDraft:
    preferred_name: str | None
    name_reason: str | None
    memory_points: tuple[AIPersonMemoryPoint, ...]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_datetime_from_text(value: object | None) -> datetime | None:
    return None if value is None else _datetime_from_text(value)


class AIPersonProfileService:
    """Persistence and prompt assembly for known-user profiles."""

    async def get_profile_by_id(
        self,
        *,
        person_id: str,
    ) -> AIPersonProfileDefinition | None:
        row = self._get_profile_row_by_id(person_id=person_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def get_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> AIPersonProfileDefinition | None:
        row = self._get_profile_row(platform=platform, user_id=user_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def ensure_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> _PersonProfileRow:
        row = self._get_profile_row(platform=platform, user_id=user_id)
        if row is not None:
            return row

        now = _utcnow()
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ai_person_profile (
                    person_id,
                    platform,
                    user_id,
                    memory_points_json,
                    is_known,
                    last_interaction,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"person_{uuid4().hex}",
                    platform,
                    user_id,
                    "[]",
                    0,
                    _datetime_to_text(now),
                    _datetime_to_text(now),
                    _datetime_to_text(now),
                ),
            )
            row_id = int(cursor.lastrowid or 0)
            inserted = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE id = ?",
                (row_id,),
            ).fetchone()
        assert inserted is not None
        return _row_to_person_profile(inserted)

    async def list_profiles(
        self,
        *,
        limit: int = 50,
    ) -> list[AIPersonProfileDefinition]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_PROFILE_FIELDS
                + """
                ORDER BY last_interaction DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._to_definition(_row_to_person_profile(row)) for row in rows]

    async def update_profile(
        self,
        *,
        person_id: str,
        person_name: str | None = None,
        nickname: str | None = None,
        memory_points: tuple[AIPersonMemoryPoint, ...] | None = None,
    ) -> AIPersonProfileDefinition | None:
        row = self._get_profile_row_by_id(person_id=person_id)
        if row is None:
            return None
        if person_name is not None:
            row.person_name = person_name or None
        if nickname is not None:
            row.nickname = nickname or None
        if memory_points is not None:
            row.memory_points_json = self._serialize_memory_points(memory_points)
        row.updated_at = _utcnow()
        self._update_profile_row(row)
        return self._to_definition(row)

    async def delete_profile(
        self,
        *,
        person_id: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_person_profile WHERE person_id = ?",
                (person_id,),
            )
            return int(cursor.rowcount or 0) > 0

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
        row = self._get_profile_row(
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

        now = _utcnow()
        row.last_interaction = now
        row.updated_at = now
        if not has_profile_signal:
            self._update_profile_row(row)
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
        self._update_profile_row(row)
        return self._to_definition(row)

    def _get_profile_row(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> _PersonProfileRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE platform = ? AND user_id = ?",
                (platform, user_id),
            ).fetchone()
        return None if row is None else _row_to_person_profile(row)

    def _get_profile_row_by_id(
        self,
        *,
        person_id: str,
    ) -> _PersonProfileRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE person_id = ?",
                (person_id,),
            ).fetchone()
        return None if row is None else _row_to_person_profile(row)

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

    @staticmethod
    def _update_profile_row(row: _PersonProfileRow) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_person_profile
                SET
                    person_name = ?,
                    nickname = ?,
                    name_reason = ?,
                    memory_points_json = ?,
                    is_known = ?,
                    know_since = ?,
                    last_interaction = ?,
                    updated_at = ?
                WHERE person_id = ?
                """,
                (
                    row.person_name,
                    row.nickname,
                    row.name_reason,
                    row.memory_points_json,
                    1 if row.is_known else 0,
                    _datetime_to_text(row.know_since),
                    _datetime_to_text(row.last_interaction),
                    _datetime_to_text(row.updated_at),
                    row.person_id,
                ),
            )

    def _to_definition(self, row: _PersonProfileRow) -> AIPersonProfileDefinition:
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


_SELECT_PROFILE_FIELDS = """
SELECT
    id,
    person_id,
    platform,
    user_id,
    person_name,
    nickname,
    name_reason,
    memory_points_json,
    is_known,
    know_since,
    last_interaction,
    created_at,
    updated_at
FROM ai_person_profile
"""


def _row_to_person_profile(row: tuple[object, ...]) -> _PersonProfileRow:
    return _PersonProfileRow(
        id=int(str(row[0])),
        person_id=str(row[1]),
        platform=str(row[2]),
        user_id=str(row[3]),
        person_name=str(row[4]) if row[4] is not None else None,
        nickname=str(row[5]) if row[5] is not None else None,
        name_reason=str(row[6]) if row[6] is not None else None,
        memory_points_json=str(row[7] or "[]"),
        is_known=bool(row[8]),
        know_since=_optional_datetime_from_text(row[9]),
        last_interaction=_datetime_from_text(row[10]),
        created_at=_datetime_from_text(row[11]),
        updated_at=_datetime_from_text(row[12]),
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
