"""SQLite persistence for AI profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import delete, select, update

from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_relationship import AIProfile

if TYPE_CHECKING:
    from apeiria.ai.profile.models import AIProfileNameSource, AIProfileNameVisibility

_NAME_SOURCES = frozenset({"manual", "self_introduced", "platform", "inferred"})
_NAME_VISIBILITIES = frozenset({"private_only", "public_allowed", "disabled"})


@dataclass
class ProfileRow:
    id: int
    profile_id: str
    platform: str
    user_id: str
    display_name: str | None
    preferred_name: str | None
    name_source: AIProfileNameSource | None
    name_visibility: AIProfileNameVisibility
    profile_enabled: bool
    last_interaction_at: datetime
    created_at: datetime
    updated_at: datetime


class ProfileRepository:
    """Own low-level SQL operations for profile persistence."""

    async def get_profile_row_by_id(
        self,
        *,
        profile_id: str,
    ) -> ProfileRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIProfile).where(AIProfile.profile_id == profile_id)
            )
            model = result.scalars().first()
        return None if model is None else _model_to_row(model)

    async def get_profile_row(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> ProfileRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIProfile).where(
                    AIProfile.platform == platform,
                    AIProfile.user_id == user_id,
                )
            )
            model = result.scalars().first()
        return None if model is None else _model_to_row(model)

    async def ensure_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> ProfileRow:
        row = await self.get_profile_row(platform=platform, user_id=user_id)
        if row is not None:
            return row

        now = _epoch_ms()
        new_profile = AIProfile(
            profile_id=f"profile_{uuid4().hex}",
            platform=platform,
            user_id=user_id,
            name_visibility="public_allowed",
            profile_enabled=1,
            last_interaction_at=now,
            created_at=now,
            updated_at=now,
        )
        async with get_session() as session:
            session.add(new_profile)
            await session.commit()
        return _model_to_row(new_profile)

    async def list_profile_rows(
        self,
        *,
        limit: int = 50,
    ) -> list[ProfileRow]:
        async with get_session() as session:
            result = await session.execute(
                select(AIProfile)
                .order_by(AIProfile.last_interaction_at.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
        return [_model_to_row(r) for r in rows]

    async def update_profile_row(self, row: ProfileRow) -> None:
        async with get_session() as session:
            await session.execute(
                update(AIProfile)
                .where(AIProfile.profile_id == row.profile_id)
                .values(
                    display_name=row.display_name,
                    preferred_name=row.preferred_name,
                    name_source=row.name_source,
                    name_visibility=row.name_visibility,
                    profile_enabled=1 if row.profile_enabled else 0,
                    last_interaction_at=_datetime_to_epoch_ms(row.last_interaction_at),
                    updated_at=_epoch_ms(),
                )
            )
            await session.commit()

    async def delete_profile(
        self,
        *,
        profile_id: str,
    ) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AIProfile).where(AIProfile.profile_id == profile_id)
            )
            await session.commit()
        return rowcount(result) > 0


def _model_to_row(model: AIProfile) -> ProfileRow:
    return ProfileRow(
        id=0,
        profile_id=model.profile_id,
        platform=model.platform,
        user_id=model.user_id,
        display_name=model.display_name,
        preferred_name=model.preferred_name,
        name_source=_coerce_name_source(model.name_source),
        name_visibility=_coerce_name_visibility(model.name_visibility),
        profile_enabled=bool(model.profile_enabled),
        last_interaction_at=_epoch_ms_to_datetime(model.last_interaction_at),
        created_at=_epoch_ms_to_datetime(model.created_at),
        updated_at=_epoch_ms_to_datetime(model.updated_at),
    )


def _epoch_ms_to_datetime(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _datetime_to_epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_name_source(value: object) -> "AIProfileNameSource | None":
    text = str(value) if value is not None else ""
    if text in _NAME_SOURCES:
        return cast("AIProfileNameSource", text)
    return None


def _coerce_name_visibility(value: object) -> "AIProfileNameVisibility":
    text = str(value) if value is not None else ""
    if text in _NAME_VISIBILITIES:
        return cast("AIProfileNameVisibility", text)
    return "public_allowed"


def datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
