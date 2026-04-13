"""Database schema bootstrap and version management."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

CURRENT_SCHEMA_VERSION = 18

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

MigrationFunc = Callable[["AsyncSession"], Awaitable[None]]

MIGRATIONS: dict[int, MigrationFunc] = {}
CORE_TABLE_NAMES = frozenset(
    {
        "ai_affinity",
        "ai_chat_model",
        "ai_conversation",
        "ai_future_task",
        "ai_memory_embedding",
        "ai_memory_item",
        "ai_model_binding",
        "ai_model_profile",
        "ai_persona",
        "ai_persona_binding",
        "ai_source",
        "ai_tool_execution",
        "ai_tool_policy_binding",
        "ai_turn",
        "apeiria_schema_meta",
        "access_policy_entry",
        "command_statistics",
        "group_console",
        "level_user",
        "plugin_info",
        "plugin_policy_entry",
        "user_console",
    }
)
LEGACY_CORE_TABLE_NAMES = frozenset(
    {
        "ban_console",
        "command_statistics",
        "group_console",
        "level_user",
        "plugin_info",
        "user_console",
    }
)
ADOPTABLE_CORE_TABLE_NAMES = frozenset(
    (CORE_TABLE_NAMES - {"apeiria_schema_meta"}) | {"ban_console"}
)


class SchemaBootstrapError(RuntimeError):
    """Raised when database schema cannot be initialized or upgraded safely."""


@dataclass(frozen=True)
class SchemaStatus:
    """Observed database schema state for Apeiria tables."""

    existing_tables: frozenset[str]
    schema_version: int | None

    @property
    def apeiria_tables(self) -> frozenset[str]:
        return frozenset(self.existing_tables & CORE_TABLE_NAMES)

    @property
    def is_uninitialized(self) -> bool:
        return not self.apeiria_tables

    @property
    def has_schema_meta(self) -> bool:
        return "apeiria_schema_meta" in self.existing_tables

    @property
    def is_partially_initialized(self) -> bool:
        return bool(self.apeiria_tables) and not self.has_schema_meta

    @property
    def can_adopt_legacy_schema(self) -> bool:
        managed_tables = self.existing_tables & ADOPTABLE_CORE_TABLE_NAMES
        return LEGACY_CORE_TABLE_NAMES <= managed_tables <= ADOPTABLE_CORE_TABLE_NAMES


async def ensure_database_ready() -> None:
    """Initialize a fresh database or verify/upgrade an existing schema."""
    from nonebot_plugin_orm import Model, get_session

    from apeiria.infra.db import models as db_models  # noqa: F401
    from apeiria.infra.db.models import SchemaMeta

    async with get_session() as session:
        conn = await session.connection()
        status = await _inspect_schema_status(conn)

        if status.is_uninitialized:
            await conn.run_sync(Model.metadata.create_all)
            session.add(SchemaMeta(id=1, schema_version=CURRENT_SCHEMA_VERSION))
            await session.commit()
            logger.info(
                "Apeiria database schema initialized automatically at version {}",
                CURRENT_SCHEMA_VERSION,
            )
            return

        if status.is_partially_initialized:
            if status.can_adopt_legacy_schema:
                await conn.run_sync(Model.metadata.create_all)
                session.add(SchemaMeta(id=1, schema_version=CURRENT_SCHEMA_VERSION))
                await session.commit()
                logger.info(
                    "Apeiria legacy database schema adopted at version {}",
                    CURRENT_SCHEMA_VERSION,
                )
                return

            msg = (
                "Detected partially initialized Apeiria database tables without "
                "schema metadata. Refusing automatic bootstrap to avoid schema drift."
            )
            raise SchemaBootstrapError(msg)

        schema_version = status.schema_version
        if schema_version is None:
            if status.apeiria_tables == CORE_TABLE_NAMES:
                await _normalize_memory_types_to_note(session)
                session.add(SchemaMeta(id=1, schema_version=CURRENT_SCHEMA_VERSION))
                await session.commit()
                logger.info(
                    "Apeiria schema metadata was repaired at version {}",
                    CURRENT_SCHEMA_VERSION,
                )
                return

            msg = "Apeiria schema metadata is missing a valid schema version."
            raise SchemaBootstrapError(msg)
        if schema_version > CURRENT_SCHEMA_VERSION:
            msg = (
                "Database schema version is newer than this Apeiria build "
                f"({schema_version} > {CURRENT_SCHEMA_VERSION})."
            )
            raise SchemaBootstrapError(msg)
        if schema_version < CURRENT_SCHEMA_VERSION:
            await _apply_migrations(session, schema_version, CURRENT_SCHEMA_VERSION)


def ensure_database_ready_sync() -> None:
    """Synchronous wrapper for startup-time schema readiness checks."""
    asyncio.run(ensure_database_ready())


async def _inspect_schema_status(conn: AsyncConnection) -> SchemaStatus:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import select

    from apeiria.infra.db.models.schema_meta import SchemaMeta

    def _collect(sync_conn):  # noqa: ANN001
        inspector = sa_inspect(sync_conn)
        return set(inspector.get_table_names())

    existing_tables = frozenset(await conn.run_sync(_collect))
    if "apeiria_schema_meta" not in existing_tables:
        return SchemaStatus(existing_tables=existing_tables, schema_version=None)

    result = await conn.execute(
        select(SchemaMeta.schema_version).order_by(SchemaMeta.id.desc()).limit(1)
    )
    schema_version = result.scalar_one_or_none()
    return SchemaStatus(
        existing_tables=existing_tables,
        schema_version=schema_version,
    )


async def _apply_migrations(
    session: AsyncSession,
    from_version: int,
    to_version: int,
) -> None:
    from sqlalchemy import select

    from apeiria.infra.db.models.schema_meta import SchemaMeta

    current_version = from_version
    while current_version < to_version:
        migration = MIGRATIONS.get(current_version)
        if migration is None:
            msg = (
                "No schema migration path is available from version "
                f"{current_version} to {current_version + 1}."
            )
            raise SchemaBootstrapError(msg)

        await migration(session)
        current_version += 1

    result = await session.execute(
        select(SchemaMeta).order_by(SchemaMeta.id.desc()).limit(1)
    )
    meta = result.scalar_one_or_none()
    if meta is None:
        meta = SchemaMeta(id=1, schema_version=current_version)
        session.add(meta)
    else:
        meta.schema_version = current_version
    await session.commit()
    logger.info(
        "Apeiria database schema upgraded from version {} to {}",
        from_version,
        current_version,
    )


async def _migrate_v1_to_v2(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[1] = _migrate_v1_to_v2


async def _migrate_v2_to_v3(session: AsyncSession) -> None:
    from sqlalchemy import text

    await session.execute(text("DROP TABLE IF EXISTS ban_console"))
    await session.commit()


MIGRATIONS[2] = _migrate_v2_to_v3


async def _migrate_v3_to_v4(session: AsyncSession) -> None:
    from sqlalchemy import text

    await session.execute(
        text(
            "ALTER TABLE plugin_policy_entry "
            "ADD COLUMN access_mode VARCHAR(16) "
            "NOT NULL DEFAULT 'default_allow'"
        )
    )
    await session.commit()


MIGRATIONS[3] = _migrate_v3_to_v4


async def _migrate_v4_to_v5(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[4] = _migrate_v4_to_v5


async def _migrate_v5_to_v6(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[5] = _migrate_v5_to_v6


async def _migrate_v6_to_v7(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[6] = _migrate_v6_to_v7


async def _migrate_v7_to_v8(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[7] = _migrate_v7_to_v8


async def _migrate_v8_to_v9(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[8] = _migrate_v8_to_v9


async def _migrate_v9_to_v10(session: AsyncSession) -> None:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    conn = await session.connection()

    def _has_scope_key(sync_conn):  # noqa: ANN001
        inspector = sa_inspect(sync_conn)
        columns = inspector.get_columns("ai_affinity")
        return any(column["name"] == "scope_key" for column in columns)

    try:
        has_scope_key = await conn.run_sync(_has_scope_key)
    except Exception:  # noqa: BLE001
        has_scope_key = False

    if not has_scope_key:
        await session.execute(
            text(
                "ALTER TABLE ai_affinity "
                "ADD COLUMN scope_key VARCHAR(160) NOT NULL DEFAULT 'private'"
            )
        )
        await session.execute(
            text(
                "UPDATE ai_affinity "
                "SET scope_key = CASE "
                "WHEN group_id IS NULL THEN 'private' "
                "ELSE 'group:' || group_id END"
            )
        )

    await session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_ai_affinity_scope_key_subject "
            "ON ai_affinity (platform, scope_key, user_id)"
        )
    )
    await session.commit()


MIGRATIONS[9] = _migrate_v9_to_v10


async def _migrate_v10_to_v11(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[10] = _migrate_v10_to_v11


async def _migrate_v11_to_v12(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)
    await session.commit()


MIGRATIONS[11] = _migrate_v11_to_v12


async def _migrate_v12_to_v13(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[12] = _migrate_v12_to_v13


async def _migrate_v13_to_v14(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)
    await session.commit()


MIGRATIONS[13] = _migrate_v13_to_v14


async def _migrate_v14_to_v15(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)


MIGRATIONS[14] = _migrate_v14_to_v15


async def _migrate_v15_to_v16(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model

    conn = await session.connection()
    await conn.run_sync(Model.metadata.create_all)
    await session.commit()


MIGRATIONS[15] = _migrate_v15_to_v16


async def _migrate_v16_to_v17(session: AsyncSession) -> None:
    from nonebot_plugin_orm import Model
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    conn = await session.connection()

    def _has_memory_domain(sync_conn):  # noqa: ANN001
        inspector = sa_inspect(sync_conn)
        columns = inspector.get_columns("ai_memory_item")
        return any(column["name"] == "memory_domain" for column in columns)

    has_memory_domain = await conn.run_sync(_has_memory_domain)
    if not has_memory_domain:
        await session.execute(
            text(
                "ALTER TABLE ai_memory_item "
                "ADD COLUMN memory_domain VARCHAR(32) NOT NULL DEFAULT 'social'"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ai_memory_item_memory_domain "
                "ON ai_memory_item (memory_domain)"
            )
        )
    await conn.run_sync(Model.metadata.create_all)
    await session.commit()


MIGRATIONS[16] = _migrate_v16_to_v17


async def _migrate_v17_to_v18(session: AsyncSession) -> None:
    await _normalize_memory_types_to_note(session)
    await session.commit()


MIGRATIONS[17] = _migrate_v17_to_v18


async def _normalize_memory_types_to_note(session: AsyncSession) -> None:
    from sqlalchemy import text

    await session.execute(
        text(
            "UPDATE ai_memory_item "
            "SET memory_type = 'note' "
            "WHERE memory_type IN ('episode', 'summary', 'operator_note')"
        )
    )
