"""Database schema bootstrap and version management."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

CURRENT_SCHEMA_VERSION = 5

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

MigrationFunc = Callable[["AsyncSession"], Awaitable[None]]

MIGRATIONS: dict[int, MigrationFunc] = {}
CORE_TABLE_NAMES = frozenset(
    {
        "ai_conversation",
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
