"""Read-only Apeiria database inspection."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.db.schema import CURRENT_SCHEMA_LINE, CURRENT_SCHEMA_VERSION

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class DatabaseSchemaInspection:
    """Observed database schema state."""

    status: str
    ready: bool
    schema_line: str | None
    schema_version: int | None
    head_schema_line: str
    head_schema_version: int
    head_revision: str
    detail: str | None = None


@dataclass(frozen=True)
class DatabaseInspection:
    """Read-only database status payload."""

    project_root: Path
    path: Path
    exists: bool
    ready: bool
    schema: DatabaseSchemaInspection


def inspect_database(project_root: Path) -> DatabaseInspection:
    """Inspect the Apeiria database without creating or changing it."""
    root = project_root.resolve()
    database_path = ApeiriaDatabase(project_root=root).database_path()
    if not database_path.exists():
        schema = DatabaseSchemaInspection(
            status="missing",
            ready=False,
            schema_line=None,
            schema_version=None,
            head_schema_line=CURRENT_SCHEMA_LINE,
            head_schema_version=CURRENT_SCHEMA_VERSION,
            head_revision=_head_revision(),
        )
        return DatabaseInspection(
            project_root=root,
            path=database_path,
            exists=False,
            ready=False,
            schema=schema,
        )

    schema = _inspect_existing_database(database_path)
    return DatabaseInspection(
        project_root=root,
        path=database_path,
        exists=True,
        ready=schema.ready,
        schema=schema,
    )


def _inspect_existing_database(
    database_path: Path,
) -> DatabaseSchemaInspection:
    schema: DatabaseSchemaInspection
    try:
        row = _read_schema_meta_row(database_path)
    except sqlite3.OperationalError as exc:
        detail = str(exc)
        status = "incompatible" if "no such table" in detail.lower() else "unreadable"
        schema = _schema_result(status=status, ready=False)
    except sqlite3.DatabaseError as exc:
        schema = _schema_result(
            status="unreadable",
            ready=False,
            detail=str(exc),
        )
    else:
        schema = _schema_from_row(row)
    return schema


def _read_schema_meta_row(database_path: Path) -> tuple[object, object] | None:
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        row = connection.execute(
            """
            SELECT schema_line, schema_version
            FROM apeiria_schema_meta
            WHERE id = 1
            """
        ).fetchone()
        return cast("tuple[object, object] | None", row)
    finally:
        connection.close()


def _schema_from_row(row: tuple[object, object] | None) -> DatabaseSchemaInspection:
    if row is None:
        return _schema_result(
            status="incompatible",
            ready=False,
        )
    try:
        schema_line = str(row[0])
        schema_version = int(str(row[1]))
    except ValueError as exc:
        return _schema_result(
            status="incompatible",
            ready=False,
            detail=str(exc),
        )
    if schema_line != CURRENT_SCHEMA_LINE:
        return _schema_result(
            status="incompatible",
            ready=False,
            schema_line=schema_line,
            schema_version=schema_version,
        )
    if schema_version != CURRENT_SCHEMA_VERSION:
        return _schema_result(
            status="unsupported",
            ready=False,
            schema_line=schema_line,
            schema_version=schema_version,
        )
    return _schema_result(
        status="current",
        ready=True,
        schema_line=schema_line,
        schema_version=schema_version,
    )


def _schema_result(
    *,
    status: str,
    ready: bool,
    schema_line: str | None = None,
    schema_version: int | None = None,
    detail: str | None = None,
) -> DatabaseSchemaInspection:
    return DatabaseSchemaInspection(
        status=status,
        ready=ready,
        schema_line=schema_line,
        schema_version=schema_version,
        head_schema_line=CURRENT_SCHEMA_LINE,
        head_schema_version=CURRENT_SCHEMA_VERSION,
        head_revision=_head_revision(),
        detail=detail,
    )


def _head_revision() -> str:
    return f"{CURRENT_SCHEMA_LINE}/{CURRENT_SCHEMA_VERSION}"
