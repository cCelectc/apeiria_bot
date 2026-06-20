"""Schema metadata constants and error types shared across the DB layer."""

from __future__ import annotations

CURRENT_SCHEMA_LINE = "apeiria_v1"
CURRENT_SCHEMA_VERSION = 3
WEBUI_AUTH_SIMPLIFIED_SCHEMA_VERSION = 2
SUPPORTED_MIGRATION_SOURCE_VERSIONS = frozenset({1, 2})

TOOL_LEVEL_VALUES: tuple[str, ...] = ("none", "read", "write", "host", "admin")
TOOL_LEVEL_CHECK = "allowed_level IN ('none', 'read', 'write', 'host', 'admin')"
TOOL_OBSERVATION_STATUS_VALUES: tuple[str, ...] = (
    "success",
    "error",
    "timeout",
    "denied",
    "not_ready",
)
TOOL_OBSERVATION_STATUS_CHECK = (
    "status IN ('success', 'error', 'timeout', 'denied', 'not_ready')"
)

SOURCE_MODEL_TABLE_NAMES: tuple[str, ...] = (
    "ai_chat_models",
    "ai_embedding_models",
    "ai_rerank_models",
)

TURN_DISPOSITION_VALUES: tuple[str, ...] = (
    "active",
    "observed",
    "generated",
    "tool",
    "system",
    "pruned",
    "summarized",
    "archived",
)
TURN_DISPOSITION_CHECK = (
    "turn_disposition IN ("
    "'active', 'observed', 'generated', 'tool', "
    "'system', 'pruned', 'summarized', 'archived')"
)
MEMORY_ANCHOR_VALUES: tuple[str, ...] = (
    "operator",
    "scene",
    "participant",
    "user",
    "project",
)
MEMORY_LIFECYCLE_VALUES: tuple[str, ...] = (
    "candidate",
    "active",
    "suppressed",
    "archived",
)
MEMORY_USE_MODE_VALUES: tuple[str, ...] = (
    "ignore",
    "silent",
    "context",
    "explicit",
)
MEMORY_ACTION_VALUES: tuple[str, ...] = (
    "accept",
    "reject",
    "reinforce",
    "revise",
    "rescope",
    "suppress",
    "activate",
    "archive",
    "supersede",
    "delete",
)
PROFILE_NAME_SOURCE_VALUES: tuple[str, ...] = (
    "manual",
    "self_introduced",
    "platform",
    "inferred",
)
PROFILE_NAME_VISIBILITY_VALUES: tuple[str, ...] = (
    "private_only",
    "public_allowed",
    "disabled",
)
RELATIONSHIP_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "message",
    "manual",
    "decay",
)
AI_MODEL_TASK_CLASS_VALUES: tuple[str, ...] = (
    "planner_light",
    "reply_default",
    "reply_roleplay",
    "reasoning_heavy",
    "memory_extraction",
    "tool_orchestration",
)
AI_MODEL_ROUTE_MODE_VALUES: tuple[str, ...] = (
    "primary_fallback",
    "load_balance",
)
AI_MODEL_ROUTE_ALGORITHM_VALUES: tuple[str, ...] = (
    "ordered",
    "weighted_random",
)
AI_MODEL_ROUTE_SCOPE_VALUES: tuple[str, ...] = (
    "global",
    "group",
    "user",
    "conversation",
)


class DatabaseSchemaError(RuntimeError):
    """Base error for Apeiria SQLite schema handling."""


class IncompatibleDatabaseError(DatabaseSchemaError):
    """Raised when the on-disk database is not compatible with Apeiria SQLite."""

    @classmethod
    def missing_schema_meta(cls) -> "IncompatibleDatabaseError":
        return cls("database exists without apeiria_v1 schema metadata")

    @classmethod
    def wrong_schema_line(cls) -> "IncompatibleDatabaseError":
        return cls("database schema line is not compatible with apeiria_v1")


class UnsupportedDatabaseVersionError(DatabaseSchemaError):
    """Raised when an unsupported SQLite schema version is encountered."""

    @classmethod
    def unsupported_schema_version(
        cls,
        *,
        observed: int,
        expected: int,
    ) -> "UnsupportedDatabaseVersionError":
        return cls(
            "database schema version "
            f"{observed} is not supported by this Apeiria build; "
            f"expected {CURRENT_SCHEMA_LINE}/{expected}"
        )

    @classmethod
    def future_schema_version(
        cls,
        *,
        observed: int,
        expected: int,
    ) -> "UnsupportedDatabaseVersionError":
        return cls(
            "database schema version "
            f"{observed} is newer than this Apeiria build supports; "
            f"use a newer build or restore a {CURRENT_SCHEMA_LINE}/{expected} backup"
        )
