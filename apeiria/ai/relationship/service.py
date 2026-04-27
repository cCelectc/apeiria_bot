"""Relationship state storage and emotion projection service."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, cast

from apeiria.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipEvent,
    AIRelationshipState,
    EmotionProjection,
)
from apeiria.ai.relationship.repository import (
    AffinityRow,
    RelationshipEventRow,
    RelationshipRepository,
    deserialize_mood_tags,
    serialize_mood_tags,
    utcnow,
)
from apeiria.ai.relationship.scope import build_affinity_scope_key
from apeiria.ai.relationship.scoring import (
    apply_inactivity_decay,
    apply_relationship_delta,
    project_emotion,
)

if TYPE_CHECKING:
    from sqlite3 import Connection

    from apeiria.ai.relationship.models import AIRelationshipEventType


class AIRelationshipService:
    """Relationship persistence and emotion projection service."""

    def __init__(
        self,
        *,
        repository: RelationshipRepository | None = None,
    ) -> None:
        self._repository = repository or RelationshipRepository()

    async def get_state_snapshot(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> tuple[float, tuple[str, ...]]:
        """Return a compact relationship snapshot for adjacent prompt systems."""
        state = await self.get_effective_state(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        return state.score, state.mood_tags

    async def get_state(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load or initialize relationship state."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return self._build_default_state(
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
        return self._to_state(row)

    async def get_effective_state(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load one relationship state with read-time decay applied in memory."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return self._build_default_state(
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
        return self._build_effective_state(row)

    async def apply_delta(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        delta: AIRelationshipDelta,
    ) -> AIRelationshipState:
        """Apply one deterministic delta and persist the updated state."""
        with self._repository.transaction_sync() as connection:
            row = self._repository.get_or_create_row(
                connection,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
            state = self._persist_inactivity_decay(connection, row)

            updated = apply_relationship_delta(state, delta)
            now = utcnow()
            row.score = updated.score
            row.mood_tags_json = serialize_mood_tags(updated.mood_tags)
            row.last_event_at = now
            row.last_decay_at = None
            self._repository.update_row(connection, row)
            self._repository.record_event(
                connection,
                affinity_id=row.affinity_id,
                platform=row.platform,
                group_id=row.group_id,
                user_id=row.user_id,
                event_type=delta.event_type,
                score_delta=updated.score - state.score,
                score_after=updated.score,
                mood_tag=delta.mood_tag,
                reason=delta.reason,
                created_at=now,
            )
        return self._to_state(row)

    async def set_manual_score(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        score: float,
    ) -> AIRelationshipState:
        """Persist an operator override for relationship score."""
        with self._repository.transaction_sync() as connection:
            row = self._repository.get_or_create_row(
                connection,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
            state = self._persist_inactivity_decay(connection, row)
            now = utcnow()
            next_score = max(-1.0, min(1.0, score))
            row.score = next_score
            row.last_event_at = now
            row.last_decay_at = None
            self._repository.update_row(connection, row)
            self._repository.record_event(
                connection,
                affinity_id=row.affinity_id,
                platform=row.platform,
                group_id=row.group_id,
                user_id=row.user_id,
                event_type="manual",
                score_delta=next_score - state.score,
                score_after=next_score,
                mood_tag=None,
                reason="manual score override",
                created_at=now,
            )
        return self._to_state(row)

    async def list_states(
        self,
        *,
        limit: int,
    ) -> list[AIRelationshipState]:
        """List recent relationship states for owner-facing management."""
        return [self._to_state(row) for row in self._repository.list_rows(limit=limit)]

    async def list_events_for_target(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        limit: int,
    ) -> list[AIRelationshipEvent]:
        """List recent events for one relationship target."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return []
        return await self.list_events(affinity_id=row.affinity_id, limit=limit)

    async def list_events(
        self,
        *,
        affinity_id: str,
        limit: int,
    ) -> list[AIRelationshipEvent]:
        """List recent persisted events for one affinity state."""
        return [
            self._to_event(row)
            for row in self._repository.list_event_rows(
                affinity_id=affinity_id,
                limit=limit,
            )
        ]

    async def project_state(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> EmotionProjection:
        """Build the current emotion projection for one user within a scene."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return project_emotion(
                self._build_default_state(
                    platform=platform,
                    group_id=group_id,
                    user_id=user_id,
                )
            )
        return project_emotion(self._build_effective_state(row))

    def _find_row(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AffinityRow | None:
        return self._repository.find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )

    def _persist_inactivity_decay(
        self,
        connection: "Connection",
        row: AffinityRow,
    ) -> AIRelationshipState:
        state = self._to_state(row)
        decayed = self._build_effective_state(row)
        if (
            decayed.score == state.score
            and decayed.mood_tags == state.mood_tags
            and decayed.last_decay_at == state.last_decay_at
        ):
            return state

        row.score = decayed.score
        row.mood_tags_json = serialize_mood_tags(decayed.mood_tags)
        row.last_decay_at = decayed.last_decay_at
        self._repository.update_row(connection, row)
        self._repository.record_event(
            connection,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type="absence_decay",
            score_delta=decayed.score - state.score,
            score_after=decayed.score,
            mood_tag=(decayed.mood_tags[-1] if decayed.mood_tags else None),
            reason="relationship drifted toward neutral after inactivity",
            created_at=row.last_decay_at or utcnow(),
        )
        return decayed

    @staticmethod
    def _build_effective_state(row: AffinityRow) -> AIRelationshipState:
        state = AIRelationshipService._to_state(row)
        return apply_inactivity_decay(
            state,
            current_time=utcnow(),
        )

    @staticmethod
    def _build_default_state(
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        scope_key = build_affinity_scope_key(group_id)
        identity = "|".join((platform, scope_key, user_id))
        return AIRelationshipState(
            affinity_id=(
                "aff_transient_"
                + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            ),
            platform=platform,
            group_id=group_id,
            user_id=user_id,
            score=0.0,
            mood_tags=(),
            last_event_at=None,
            last_decay_at=None,
        )

    @staticmethod
    def _to_state(row: AffinityRow) -> AIRelationshipState:
        mood_tags = deserialize_mood_tags(row.mood_tags_json)
        return AIRelationshipState(
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            score=row.score,
            mood_tags=mood_tags,
            last_event_at=row.last_event_at,
            last_decay_at=row.last_decay_at,
        )

    @staticmethod
    def _to_event(row: RelationshipEventRow) -> AIRelationshipEvent:
        return AIRelationshipEvent(
            event_id=row.event_id,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type=cast("AIRelationshipEventType", row.event_type),
            score_delta=row.score_delta,
            score_after=row.score_after,
            mood_tag=row.mood_tag,
            reason=row.reason,
            created_at=row.created_at,
        )


ai_relationship_service = AIRelationshipService()
