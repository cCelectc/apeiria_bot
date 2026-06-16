"""AI-owned runtime behavior settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings as AIRuntimeSettingsModel

AIRuntimeSettingKey = Literal[
    "allow_group_initiative",
    "quiet_hours_enabled",
    "quiet_hours_start_minute",
    "quiet_hours_end_minute",
    "night_awake_lease_minutes",
    "stt_input_enabled",
    "persist_raw_event_payloads",
    "ambient_merge_window_ms",
    "max_pending_messages",
    "group_reply_cooldown_seconds",
    "max_consecutive_ambient_replies",
    "direct_bypass_ambient_budget",
    "duplicate_event_ttl_seconds",
    "tool_execution_timeout_seconds",
    "cleanup_interval_minutes",
    "conversation_retention_days",
    "raw_event_retention_days",
    "tool_execution_retention_days",
    "suppressed_memory_retention_days",
]
AIRuntimeSettingGroup = Literal[
    "reply_policy",
    "ingress_media",
    "runtime_limits",
    "retention",
]
AIRuntimeSettingApplication = Literal[
    "next_turn",
    "next_session_runtime",
    "next_cleanup",
]
AIRuntimeSettingVisibility = Literal[
    "default",
    "advanced",
    "hidden",
]

AI_RUNTIME_SETTING_KEYS: tuple[AIRuntimeSettingKey, ...] = get_args(AIRuntimeSettingKey)
_BOOLEAN_SETTING_KEYS: frozenset[AIRuntimeSettingKey] = frozenset(
    {
        "allow_group_initiative",
        "quiet_hours_enabled",
        "stt_input_enabled",
        "persist_raw_event_payloads",
        "direct_bypass_ambient_budget",
    }
)


class AIRuntimeSettings(BaseModel):
    """Effective AI runtime behavior settings."""

    model_config = ConfigDict(extra="forbid", strict=True)

    allow_group_initiative: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start_minute: int = Field(default=0, ge=0, le=1439)
    quiet_hours_end_minute: int = Field(default=420, ge=0, le=1439)
    night_awake_lease_minutes: int = Field(default=5, ge=1, le=120)
    stt_input_enabled: bool = False
    persist_raw_event_payloads: bool = False
    ambient_merge_window_ms: int = Field(default=1500, ge=0)
    max_pending_messages: int = Field(default=12, ge=1)
    group_reply_cooldown_seconds: int = Field(default=180, ge=0)
    max_consecutive_ambient_replies: int = Field(default=1, ge=0)
    direct_bypass_ambient_budget: bool = True
    duplicate_event_ttl_seconds: int = Field(default=30, ge=1)
    tool_execution_timeout_seconds: float = Field(default=8.0, gt=0)
    cleanup_interval_minutes: int = Field(default=30, ge=1)
    conversation_retention_days: int = Field(default=30, ge=1)
    raw_event_retention_days: int = Field(default=7, ge=1)
    tool_execution_retention_days: int = Field(default=30, ge=1)
    suppressed_memory_retention_days: int = Field(default=30, ge=1)


@dataclass(frozen=True, slots=True)
class AIRuntimeSettingField:
    """Metadata for one operator-facing AI runtime setting."""

    key: AIRuntimeSettingKey
    label: str
    help: str
    group: AIRuntimeSettingGroup
    value_type: str
    application: AIRuntimeSettingApplication
    visibility: AIRuntimeSettingVisibility = "default"
    order: int = 0
    minimum: float | None = None

    @property
    def label_key(self) -> str:
        return f"ai.runtimeSettings.fields.{_locale_key(self.key)}.label"

    @property
    def help_key(self) -> str:
        return f"ai.runtimeSettings.fields.{_locale_key(self.key)}.help"


@dataclass(frozen=True, slots=True)
class AIRuntimeSettingsView:
    """Effective settings plus default and override metadata."""

    effective: AIRuntimeSettings
    defaults: AIRuntimeSettings
    overrides: dict[AIRuntimeSettingKey, object]
    fields: tuple[AIRuntimeSettingField, ...]
    updated_at: str | None = None


AI_RUNTIME_SETTING_FIELDS: tuple[AIRuntimeSettingField, ...] = (
    AIRuntimeSettingField(
        key="allow_group_initiative",
        label="Group initiative",
        help="Allow non-mention group messages to become ambient reply candidates.",
        group="reply_policy",
        value_type="boolean",
        application="next_turn",
        order=10,
    ),
    AIRuntimeSettingField(
        key="quiet_hours_enabled",
        label="Quiet hours",
        help="Enable night-time quiet-hour reply gating for live AI turns.",
        group="reply_policy",
        value_type="boolean",
        application="next_turn",
        order=15,
    ),
    AIRuntimeSettingField(
        key="quiet_hours_start_minute",
        label="Quiet hours start",
        help="Minute of day when quiet hours begin, in local runtime time.",
        group="reply_policy",
        value_type="integer",
        application="next_turn",
        visibility="advanced",
        order=16,
        minimum=0,
    ),
    AIRuntimeSettingField(
        key="quiet_hours_end_minute",
        label="Quiet hours end",
        help="Minute of day when quiet hours end, in local runtime time.",
        group="reply_policy",
        value_type="integer",
        application="next_turn",
        visibility="advanced",
        order=17,
        minimum=0,
    ),
    AIRuntimeSettingField(
        key="night_awake_lease_minutes",
        label="Night awake lease",
        help=(
            "Minutes that one session stays responsive after a directed "
            "night-time turn."
        ),
        group="reply_policy",
        value_type="integer",
        application="next_session_runtime",
        visibility="advanced",
        order=18,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="ambient_merge_window_ms",
        label="Ambient merge window",
        help="Milliseconds used to merge short ambient group-message bursts.",
        group="reply_policy",
        value_type="integer",
        application="next_session_runtime",
        visibility="advanced",
        order=20,
        minimum=0,
    ),
    AIRuntimeSettingField(
        key="max_pending_messages",
        label="Pending message limit",
        help="Maximum pending ambient messages retained for one AI turn.",
        group="reply_policy",
        value_type="integer",
        application="next_session_runtime",
        visibility="advanced",
        order=30,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="group_reply_cooldown_seconds",
        label="Group reply cooldown",
        help="Cooldown for default ambient group-chat AI replies.",
        group="reply_policy",
        value_type="integer",
        application="next_session_runtime",
        visibility="advanced",
        order=40,
        minimum=0,
    ),
    AIRuntimeSettingField(
        key="max_consecutive_ambient_replies",
        label="Consecutive ambient replies",
        help="Maximum consecutive AI replies to ambient group messages.",
        group="reply_policy",
        value_type="integer",
        application="next_session_runtime",
        visibility="advanced",
        order=50,
        minimum=0,
    ),
    AIRuntimeSettingField(
        key="direct_bypass_ambient_budget",
        label="Direct signal bypass",
        help=(
            "Let direct mentions, private messages, and future tasks bypass "
            "ambient budget."
        ),
        group="reply_policy",
        value_type="boolean",
        application="next_session_runtime",
        visibility="advanced",
        order=60,
    ),
    AIRuntimeSettingField(
        key="duplicate_event_ttl_seconds",
        label="Duplicate event TTL",
        help="Seconds to keep local duplicate event protection entries.",
        group="reply_policy",
        value_type="integer",
        application="next_session_runtime",
        visibility="hidden",
        order=70,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="stt_input_enabled",
        label="Speech-to-text input",
        help="Enable speech-to-text preparation for incoming audio media.",
        group="ingress_media",
        value_type="boolean",
        application="next_turn",
        order=10,
    ),
    AIRuntimeSettingField(
        key="persist_raw_event_payloads",
        label="Persist raw event payloads",
        help="Persist reduced raw event payloads for AI debugging and inspection.",
        group="ingress_media",
        value_type="boolean",
        application="next_turn",
        order=20,
    ),
    AIRuntimeSettingField(
        key="tool_execution_timeout_seconds",
        label="Tool execution timeout",
        help="Maximum seconds allowed for one AI tool execution.",
        group="runtime_limits",
        value_type="float",
        application="next_turn",
        order=10,
        minimum=0.001,
    ),
    AIRuntimeSettingField(
        key="cleanup_interval_minutes",
        label="Cleanup interval",
        help="Minimum interval between automatic AI retention cleanup runs.",
        group="retention",
        value_type="integer",
        application="next_cleanup",
        visibility="advanced",
        order=10,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="conversation_retention_days",
        label="Conversation retention",
        help="Retention window for persisted AI chat messages.",
        group="retention",
        value_type="integer",
        application="next_cleanup",
        visibility="advanced",
        order=20,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="raw_event_retention_days",
        label="Raw event retention",
        help="Retention window for reduced persisted raw event payloads.",
        group="retention",
        value_type="integer",
        application="next_cleanup",
        visibility="advanced",
        order=30,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="tool_execution_retention_days",
        label="Tool execution retention",
        help="Retention window for AI tool execution audit rows.",
        group="retention",
        value_type="integer",
        application="next_cleanup",
        visibility="advanced",
        order=40,
        minimum=1,
    ),
    AIRuntimeSettingField(
        key="suppressed_memory_retention_days",
        label="Suppressed memory retention",
        help="Retention window for suppressed AI memory rows.",
        group="retention",
        value_type="integer",
        application="next_cleanup",
        visibility="advanced",
        order=50,
        minimum=1,
    ),
)


def default_ai_runtime_settings() -> AIRuntimeSettings:
    """Return the default effective AI runtime settings."""

    return AIRuntimeSettings()


class AIRuntimeSettingsRepository:
    """Async persistence for AI-owned runtime settings overrides."""

    async def get_overrides(
        self,
    ) -> tuple[dict[AIRuntimeSettingKey, object], str | None]:
        async with get_session() as session:
            result = await session.execute(
                select(AIRuntimeSettingsModel).where(AIRuntimeSettingsModel.id == 1)
            )
            model = result.scalars().first()
        if model is None:
            return {}, None

        overrides: dict[AIRuntimeSettingKey, object] = {}
        for key in AI_RUNTIME_SETTING_KEYS:
            value = getattr(model, key, None)
            if value is None:
                continue
            overrides[key] = _decode_storage_value(key, value)
        return overrides, datetime.fromtimestamp(
            model.updated_at / 1000, tz=timezone.utc
        ).isoformat()

    async def update_overrides(
        self,
        values: dict[AIRuntimeSettingKey, object],
        *,
        clear: list[AIRuntimeSettingKey] | None = None,
    ) -> tuple[dict[AIRuntimeSettingKey, object], str | None]:
        updates = dict(values)
        for key in clear or []:
            updates[key] = None
        if not updates:
            return await self.get_overrides()

        now = _epoch_ms()
        insert_values: dict[str, object] = {"id": 1, "updated_at": now}
        for key in AI_RUNTIME_SETTING_KEYS:
            insert_values[key] = _encode_storage_value(key, updates.get(key))

        set_clause: dict[str, object] = {"updated_at": now}
        for key, value in updates.items():
            set_clause[key] = _encode_storage_value(key, value)

        stmt = insert(AIRuntimeSettingsModel).values(**insert_values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AIRuntimeSettingsModel.id],
            set_=set_clause,
        )
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()
        return await self.get_overrides()


class AIRuntimeSettingsService:
    """Domain service for effective AI runtime behavior settings."""

    def __init__(
        self,
        repository: AIRuntimeSettingsRepository | None = None,
    ) -> None:
        self._repository = repository or AIRuntimeSettingsRepository()

    async def get_view(self) -> AIRuntimeSettingsView:
        defaults = default_ai_runtime_settings()
        overrides, updated_at = await self._repository.get_overrides()
        effective = _build_effective_settings(defaults, overrides)
        return AIRuntimeSettingsView(
            effective=effective,
            defaults=defaults,
            overrides=overrides,
            fields=AI_RUNTIME_SETTING_FIELDS,
            updated_at=updated_at,
        )

    async def get_settings(self) -> AIRuntimeSettings:
        """Return effective runtime settings for runtime callers."""

        return (await self.get_view()).effective

    async def update_settings(
        self,
        values: dict[str, object],
        *,
        clear: list[str] | None = None,
    ) -> AIRuntimeSettingsView:
        normalized_values: dict[AIRuntimeSettingKey, object] = {
            _coerce_setting_key(key): value for key, value in values.items()
        }
        normalized_clear: list[AIRuntimeSettingKey] = [
            _coerce_setting_key(key) for key in clear or []
        ]
        current_overrides, _ = await self._repository.get_overrides()
        next_overrides: dict[AIRuntimeSettingKey, object | None] = {
            **current_overrides,
            **normalized_values,
            **dict.fromkeys(normalized_clear, None),
        }
        _build_effective_settings(
            default_ai_runtime_settings(),
            next_overrides,
        )
        await self._repository.update_overrides(
            normalized_values,
            clear=normalized_clear,
        )
        return await self.get_view()


def _build_effective_settings(
    defaults: AIRuntimeSettings,
    overrides: dict[AIRuntimeSettingKey, object | None],
) -> AIRuntimeSettings:
    payload: dict[str, object] = {
        **defaults.model_dump(mode="python"),
        **{key: value for key, value in overrides.items() if value is not None},
    }
    return AIRuntimeSettings.model_validate(payload)


def _coerce_setting_key(key: str) -> AIRuntimeSettingKey:
    if key not in AI_RUNTIME_SETTING_KEYS:
        msg = f"unknown AI runtime setting {key}"
        raise ValueError(msg)
    return key  # type: ignore[return-value]


def _encode_storage_value(
    key: AIRuntimeSettingKey,
    value: object | None,
) -> object | None:
    if value is None:
        return None
    if key in _BOOLEAN_SETTING_KEYS:
        return 1 if bool(value) else 0
    return value


def _decode_storage_value(key: AIRuntimeSettingKey, value: object) -> object:
    if key in _BOOLEAN_SETTING_KEYS:
        return bool(value)
    return value


def _locale_key(key: AIRuntimeSettingKey) -> str:
    parts = str(key).split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


ai_runtime_settings_service = AIRuntimeSettingsService()

__all__ = [
    "AI_RUNTIME_SETTING_FIELDS",
    "AI_RUNTIME_SETTING_KEYS",
    "AIRuntimeSettingField",
    "AIRuntimeSettingKey",
    "AIRuntimeSettingVisibility",
    "AIRuntimeSettings",
    "AIRuntimeSettingsRepository",
    "AIRuntimeSettingsService",
    "AIRuntimeSettingsView",
    "ai_runtime_settings_service",
    "default_ai_runtime_settings",
]
