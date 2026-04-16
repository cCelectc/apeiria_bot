"""Person profile storage and prompt-building service."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.memory.extraction import select_person_profile_candidates
from apeiria.app.ai.person.models import (
    AIPersonMemoryPoint,
    AIPersonMemoryPointCategory,
    AIPersonProfileDefinition,
    AIPersonPromptProfile,
)
from apeiria.app.ai.relationship.service import ai_relationship_service
from apeiria.infra.db.models import AIPersonProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.memory.models import AIMemoryExtractionCandidate

_MAX_STORED_MEMORY_POINTS = 12
_MAX_PROMPT_POINTS_PER_CATEGORY = 2
_NAME_PATTERNS = (
    re.compile(
        r"(?:我叫|叫我|你可以叫我|可以叫我|喊我)"
        r"(?P<name>[A-Za-z0-9_\-\u4e00-\u9fff·]{1,16})"
    ),
)
_POSITIVE_PREFERENCE_PATTERNS = (
    re.compile(r"我(?:很|最|一直)?(?:喜欢|爱)(?P<item>[^，。！？,.!?]{1,24})"),
)
_NEGATIVE_PREFERENCE_PATTERNS = (
    re.compile(r"我(?:很|最|一直)?(?:不喜欢|讨厌)(?P<item>[^，。！？,.!?]{1,24})"),
)
_FACT_PATTERNS = (re.compile(r"我是(?P<fact>[^，。！？,.!?]{1,24})"),)
_CANDIDATE_MIN_CONFIDENCE = 0.6
_PROMPT_CATEGORY_LABELS: dict[AIPersonMemoryPointCategory, str] = {
    "preference": "Stable preference",
    "fact": "Stable fact",
    "relationship": "Relationship clue",
    "impression": "Impression point",
}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class _ProfileDraft:
    preferred_name: str | None
    name_reason: str | None
    memory_points: tuple[AIPersonMemoryPoint, ...]


class AIPersonProfileService:
    """Persistence and prompt assembly for known-user profiles."""

    async def get_profile(
        self,
        session: "AsyncSession",
        *,
        platform: str,
        user_id: str,
    ) -> AIPersonProfileDefinition | None:
        result = await session.execute(
            select(AIPersonProfile).where(
                AIPersonProfile.platform == platform,
                AIPersonProfile.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_definition(row)

    async def ensure_profile(
        self,
        session: "AsyncSession",
        *,
        platform: str,
        user_id: str,
    ) -> AIPersonProfile:
        result = await session.execute(
            select(AIPersonProfile).where(
                AIPersonProfile.platform == platform,
                AIPersonProfile.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = AIPersonProfile(
                person_id=f"person_{uuid4().hex}",
                platform=platform,
                user_id=user_id,
                memory_points_json="[]",
                is_known=False,
                last_interaction=_utcnow_naive(),
            )
            session.add(row)
            await session.flush()
        return row

    async def ingest_message(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        *,
        platform: str,
        user_id: str,
        message_text: str,
        source_message_id: str | None,
        candidates: tuple[AIMemoryExtractionCandidate, ...] = (),
    ) -> AIPersonProfileDefinition | None:
        draft = _build_profile_draft(
            message_text,
            source_message_id=source_message_id,
            candidates=candidates,
        )
        has_profile_signal = _has_profile_signal(draft)
        row = await self._get_profile_row(
            session,
            platform=platform,
            user_id=user_id,
        )
        if row is None and not has_profile_signal:
            return None
        if row is None:
            row = await self.ensure_profile(
                session,
                platform=platform,
                user_id=user_id,
            )

        now = _utcnow_naive()
        row.last_interaction = now
        if not has_profile_signal:
            await session.flush()
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
        await session.flush()
        return self._to_definition(row)

    async def _get_profile_row(
        self,
        session: "AsyncSession",
        *,
        platform: str,
        user_id: str,
    ) -> AIPersonProfile | None:
        result = await session.execute(
            select(AIPersonProfile).where(
                AIPersonProfile.platform == platform,
                AIPersonProfile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def build_prompt_profile(
        self,
        session: "AsyncSession",
        *,
        platform: str,
        user_id: str,
        group_id: str | None,
    ) -> AIPersonPromptProfile | None:
        profile = await self.get_profile(
            session,
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
            session,
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

    def _to_definition(self, row: AIPersonProfile) -> AIPersonProfileDefinition:
        created_at = (
            row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at
        )
        updated_at = (
            row.updated_at.replace(tzinfo=timezone.utc)
            if row.updated_at.tzinfo is None
            else row.updated_at
        )
        know_since = (
            row.know_since.replace(tzinfo=timezone.utc)
            if row.know_since is not None and row.know_since.tzinfo is None
            else row.know_since
        )
        last_interaction = (
            row.last_interaction.replace(tzinfo=timezone.utc)
            if row.last_interaction.tzinfo is None
            else row.last_interaction
        )
        return AIPersonProfileDefinition(
            person_id=row.person_id,
            platform=row.platform,
            user_id=row.user_id,
            person_name=row.person_name,
            nickname=row.nickname,
            name_reason=row.name_reason,
            memory_points=self._deserialize_memory_points(row.memory_points_json),
            is_known=row.is_known,
            know_since=know_since,
            last_interaction=last_interaction,
            created_at=created_at,
            updated_at=updated_at,
        )


def _build_profile_draft(
    message_text: str,
    *,
    source_message_id: str | None,
    candidates: tuple[AIMemoryExtractionCandidate, ...],
) -> _ProfileDraft:
    explicit_name = _extract_explicit_name(message_text)
    points = list(_extract_explicit_points(message_text, source_message_id))
    for candidate in select_person_profile_candidates(list(candidates)):
        point = _candidate_to_memory_point(candidate, source_message_id)
        if point is not None:
            points.append(point)
    return _ProfileDraft(
        preferred_name=explicit_name,
        name_reason="self_introduced" if explicit_name else None,
        memory_points=tuple(points),
    )


def _has_profile_signal(draft: _ProfileDraft) -> bool:
    return bool(draft.preferred_name or draft.memory_points)


def _extract_explicit_name(message_text: str) -> str | None:
    for pattern in _NAME_PATTERNS:
        match = pattern.search(message_text)
        if match is None:
            continue
        return _clean_fragment(match.group("name"))
    return None


def _extract_explicit_points(
    message_text: str,
    source_message_id: str | None,
) -> tuple[AIPersonMemoryPoint, ...]:
    points: list[AIPersonMemoryPoint] = []
    for pattern in _POSITIVE_PREFERENCE_PATTERNS:
        match = pattern.search(message_text)
        if match is None:
            continue
        item = _clean_fragment(match.group("item"))
        if item:
            points.append(
                AIPersonMemoryPoint(
                    category="preference",
                    content=f"喜欢{item}",
                    confidence=0.9,
                    source_message_id=source_message_id,
                )
            )
    for pattern in _NEGATIVE_PREFERENCE_PATTERNS:
        match = pattern.search(message_text)
        if match is None:
            continue
        item = _clean_fragment(match.group("item"))
        if item:
            points.append(
                AIPersonMemoryPoint(
                    category="preference",
                    content=f"不喜欢{item}",
                    confidence=0.9,
                    source_message_id=source_message_id,
                )
            )
    for pattern in _FACT_PATTERNS:
        match = pattern.search(message_text)
        if match is None:
            continue
        fact = _clean_fragment(match.group("fact"))
        if fact:
            points.append(
                AIPersonMemoryPoint(
                    category="fact",
                    content=f"是{fact}",
                    confidence=0.82,
                    source_message_id=source_message_id,
                )
            )
    return tuple(points)


def _candidate_to_memory_point(
    candidate: AIMemoryExtractionCandidate,
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


def _clean_fragment(fragment: str | None) -> str | None:
    if not fragment:
        return None
    value = fragment.strip().strip(" \t\r\n,，。.!！？")
    return value or None


ai_person_profile_service = AIPersonProfileService()
