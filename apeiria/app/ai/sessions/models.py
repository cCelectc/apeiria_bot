"""AI session read models for browsing and workbench preview surfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory import AIMemoryDefinition

AISessionMessageType = Literal["group", "private", "web_chat"]

_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}$")
_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REJECTED_PAYLOAD_FIELDS = {
    "origin_rule": "origin rule fields are not supported for AI sessions",
    "origin_rules": "origin rule fields are not supported for AI sessions",
    "match_criteria": "origin match criteria are not supported for AI sessions",
    "wildcard_rule": "wildcard rules are not supported for AI sessions",
    "priority_rule": "priority rules are not supported for AI sessions",
    "scene_profile": "scene profile fields are not supported for AI sessions",
    "scene_profile_id": "scene profile fields are not supported for AI sessions",
    "profile_bundle": "scene profile bundles are not supported for AI sessions",
    "conversation_id": "multi-conversation switching is not supported for AI sessions",
    "conversation_ids": "multi-conversation switching is not supported for AI sessions",
    "conversations": "multi-conversation switching is not supported for AI sessions",
}
_UNSET = object()


class AISessionValidationError(ValueError):
    """Raised when an AI session management payload is not valid for v1."""

    @classmethod
    def invalid_ai_enabled(cls) -> "AISessionValidationError":
        return cls("ai_enabled must be a boolean")

    @classmethod
    def unsupported_identifier(cls, field_name: str) -> "AISessionValidationError":
        return cls(f"{field_name} has an unsupported shape")

    @classmethod
    def invalid_optional_identifier(
        cls,
        field_name: str,
    ) -> "AISessionValidationError":
        return cls(f"{field_name} must be a string or null")

    @classmethod
    def invalid_mapping_key(cls, field_name: str) -> "AISessionValidationError":
        return cls(f"{field_name} keys must be strings")

    @classmethod
    def invalid_mapping_value(cls, field_name: str) -> "AISessionValidationError":
        return cls(f"{field_name} values must be strings")


class UnknownAISessionPersonaError(AISessionValidationError):
    """Raised when a persona override references an unknown persona."""

    @classmethod
    def for_persona_id(cls, persona_id: str) -> "UnknownAISessionPersonaError":
        return cls(f"persona_id does not exist: {persona_id}")


@dataclass(frozen=True)
class NormalizedAISessionIdentity:
    """Stable v1 AI management identity for one normalized chat source."""

    session_id: str
    platform_id: str
    platform_type: str
    message_type: AISessionMessageType
    subject_id: str

    def __post_init__(self) -> None:
        _validate_identifier("session_id", self.session_id, pattern=_SESSION_ID_PATTERN)
        _validate_identifier("platform_id", self.platform_id)
        _validate_identifier("platform_type", self.platform_type)
        _validate_identifier("subject_id", self.subject_id)


@dataclass(frozen=True)
class AISessionSourceIdentity:
    """Source facts and operator-facing labels for one managed AI session."""

    identity: NormalizedAISessionIdentity
    source_labels: dict[str, str] = field(default_factory=dict)
    diagnostic_raw_ids: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_labels",
            _clean_string_mapping("source_labels", self.source_labels),
        )
        object.__setattr__(
            self,
            "diagnostic_raw_ids",
            _clean_string_mapping("diagnostic_raw_ids", self.diagnostic_raw_ids),
        )


@dataclass(frozen=True)
class AISessionManagementRecord:
    """Administrator-managed v1 state for one AI session."""

    session_id: str
    source_identity: AISessionSourceIdentity
    ai_enabled: bool
    persona_id: str | None
    context_reset_at: datetime | None
    context_reset_by: str | None
    last_observed_at: datetime | None
    last_user_message_at: datetime | None
    last_ai_message_at: datetime | None
    created_at: datetime
    updated_at: datetime
    audit_created_by: str | None
    audit_updated_by: str | None


@dataclass(frozen=True)
class AISessionPersonaSummary:
    """Small persona summary embedded in managed session read models."""

    persona_id: str
    name: str
    enabled: bool


@dataclass(frozen=True)
class AISessionInventoryItem:
    """Operator-facing list item for one managed AI session."""

    session_id: str
    source_identity: AISessionSourceIdentity
    source_labels: dict[str, str]
    ai_enabled: bool
    persona: AISessionPersonaSummary | None
    last_observed_at: datetime | None
    last_message_at: datetime | None
    message_count: int
    diagnostic_count: int


@dataclass(frozen=True)
class AISessionDetailMessage:
    """Recent message row with reset-boundary diagnostics."""

    message_id: str
    author_role: str
    author_id: str
    text_content: str
    created_at: datetime
    before_reset_boundary: bool
    trace_id: str | None = None
    model_name: str | None = None


@dataclass(frozen=True)
class AISessionPromptPreviewEntry:
    """Link target for the prompt preview surface."""

    session_id: str
    available: bool


@dataclass(frozen=True)
class AISessionTraceEntry:
    """Compact trace link for one session detail view."""

    trace_id: str
    terminal_status: str
    skip_reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class AISessionDetail:
    """Operator-facing detail read model for one managed AI session."""

    session_id: str
    source_identity: AISessionSourceIdentity
    ai_enabled: bool
    persona: AISessionPersonaSummary | None
    recent_messages: tuple[AISessionDetailMessage, ...]
    reset_boundary_at: datetime | None
    prompt_preview_entry: AISessionPromptPreviewEntry
    trace_entries: tuple[AISessionTraceEntry, ...]
    model_summary: dict[str, str | None]
    strategy_summary: dict[str, str | None]
    tool_summary: dict[str, int]
    diagnostics: dict[str, str | None]


@dataclass(frozen=True)
class AISessionManagementUpdate:
    """Partial v1 management update for an AI session."""

    ai_enabled: bool | None = None
    persona_id: str | None | object = _UNSET
    actor_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AISessionManagementUpdate":
        validate_session_management_payload(payload)
        ai_enabled = payload.get("ai_enabled")
        if ai_enabled is not None and not isinstance(ai_enabled, bool):
            raise AISessionValidationError.invalid_ai_enabled()
        persona_id: str | None | object = _UNSET
        if "persona_id" in payload:
            persona_id = _normalize_optional_identifier(
                "persona_id",
                payload.get("persona_id"),
            )
        actor_id = _normalize_optional_identifier("actor_id", payload.get("actor_id"))
        return cls(
            ai_enabled=ai_enabled,
            persona_id=persona_id,
            actor_id=actor_id,
        )

    @property
    def updates_persona(self) -> bool:
        return self.persona_id is not _UNSET

    @property
    def normalized_persona_id(self) -> str | None:
        if self.persona_id is _UNSET:
            return None
        return self.persona_id if isinstance(self.persona_id, str) else None


def validate_session_management_payload(payload: dict[str, Any]) -> None:
    """Reject unsupported v1 fields before accepting session management input."""

    for field_name, message in _REJECTED_PAYLOAD_FIELDS.items():
        if field_name in payload:
            raise AISessionValidationError(message)


def _validate_identifier(
    field_name: str,
    value: str,
    *,
    pattern: re.Pattern[str] = _COMPONENT_PATTERN,
) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise AISessionValidationError.unsupported_identifier(field_name)


def _normalize_optional_identifier(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        _validate_identifier(field_name, normalized, pattern=_SESSION_ID_PATTERN)
        return normalized
    raise AISessionValidationError.invalid_optional_identifier(field_name)


def _clean_string_mapping(field_name: str, payload: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            raise AISessionValidationError.invalid_mapping_key(field_name)
        if not isinstance(value, str):
            raise AISessionValidationError.invalid_mapping_value(field_name)
        cleaned[key.strip()] = value
    return cleaned


@dataclass(frozen=True)
class AIRecentTarget:
    """Owner-facing recent target for browsing AI state."""

    target_type: str
    anchor_type: str
    anchor_id: str
    title: str
    subtitle: str | None
    scene_id: str | None
    platform: str | None
    scope_type: str | None
    scope_id: str | None
    user_id: str | None
    last_active_at: str | None


@dataclass(frozen=True)
class AISessionPromptSection:
    """One packet-derived prompt section exposed to preview surfaces."""

    role: str
    name: str
    content: str


@dataclass(frozen=True)
class AISessionPromptDiagnostics:
    """Bounded region metadata for one composed runtime prompt."""

    prompt_purpose: str
    stable_section_names: tuple[str, ...]
    dynamic_section_names: tuple[str, ...]
    stable_section_count: int
    dynamic_section_count: int
    total_section_count: int


@dataclass(frozen=True)
class AISessionPromptChannels:
    """Structured prompt channels for one composed runtime prompt."""

    mode: str
    system_instructions: tuple[str, ...]
    persona: str
    style: str | None
    relationship: str | None
    person_profile: tuple[str, ...]
    social_policy: str | None
    tool_policy: str | None
    future_task: str | None
    tool_results: tuple[str, ...]
    operator_memories: tuple[str, ...]
    summary_memories: tuple[str, ...]
    long_term_memories: tuple[str, ...]
    knowledge_memories: tuple[str, ...]
    conversation_summary: str | None
    context_priority: tuple[str, ...]
    conversation_messages: tuple[str, ...]
    response_rules: tuple[str, ...]
    instruction: str
    sections: tuple[AISessionPromptSection, ...] = ()


@dataclass(frozen=True)
class AISessionPromptPreview:
    """Workbench prompt/context preview for one conversation."""

    session_id: str
    latest_user_message: str | None
    planning_source_id: str | None
    planning_profile_id: str | None
    planning_model_name: str | None
    planning_task_class: str | None
    roleplay_source_id: str | None
    roleplay_profile_id: str | None
    roleplay_model_name: str | None
    roleplay_task_class: str | None
    source_id: str | None
    profile_id: str | None
    model_name: str | None
    persona_id: str | None
    conversation_summary: str | None
    relationship_context: str | None
    tool_policy: str | None
    hard_rule_action: str | None
    hard_rule_reason_text: str | None
    hard_rule_reason_codes: tuple[str, ...]
    social_action: str | None
    social_tool_mode: str | None
    social_reason_text: str | None
    social_reason_codes: tuple[str, ...]
    social_policy_source: str | None
    preview_diagnostics: tuple[str, ...]
    tool_results: tuple[str, ...]
    memories: tuple["AIMemoryDefinition", ...]
    operator_memory_count: int
    summary_memory_count: int
    long_term_memory_count: int
    knowledge_memory_count: int
    planning_prompt_diagnostics: AISessionPromptDiagnostics
    roleplay_prompt_diagnostics: AISessionPromptDiagnostics | None
    planning_channels: AISessionPromptChannels
    roleplay_channels: AISessionPromptChannels | None
    rendered_roleplay_prompt: str | None
    rendered_prompt: str
