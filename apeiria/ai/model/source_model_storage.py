"""SQLite storage helpers for admin-managed source models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from json import dumps
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime
from apeiria.db.schema import SOURCE_MODEL_TABLE_NAMES
from apeiria.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from sqlite3 import Connection


class UnsupportedSourceModelTableError(ValueError):
    """Raised when source model storage is asked to use an unknown table."""

    def __init__(self, table_name: str) -> None:
        super().__init__(f"unsupported source model table: {table_name}")


@dataclass(frozen=True)
class SourceModelRecord:
    """One persisted source model record."""

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool
    is_default: bool
    extra_params: dict[str, object]


def get_source_model(table_name: str, *, model_id: str) -> SourceModelRecord | None:
    table_name = _coerce_table_name(table_name)
    with database_runtime.connect_sync() as connection:
        row = connection.execute(
            f"""
            SELECT
                model_id,
                source_id,
                model_identifier,
                display_name,
                enabled,
                is_default,
                extra_params_json
            FROM {table_name}
            WHERE model_id = ?
            """,
            (model_id,),
        ).fetchone()
    return _row_to_record(row)


def list_source_models(
    table_name: str,
    *,
    source_id: str,
) -> list[SourceModelRecord]:
    table_name = _coerce_table_name(table_name)
    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            f"""
            SELECT
                model_id,
                source_id,
                model_identifier,
                display_name,
                enabled,
                is_default,
                extra_params_json
            FROM {table_name}
            WHERE source_id = ?
            ORDER BY is_default DESC, display_name ASC, model_id ASC
            """,
            (source_id,),
        ).fetchall()
    return [record for row in rows if (record := _row_to_record(row)) is not None]


def list_all_source_models(table_name: str) -> list[SourceModelRecord]:
    table_name = _coerce_table_name(table_name)
    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            f"""
            SELECT
                model_id,
                source_id,
                model_identifier,
                display_name,
                enabled,
                is_default,
                extra_params_json
            FROM {table_name}
            ORDER BY source_id ASC, is_default DESC, display_name ASC, model_id ASC
            """
        ).fetchall()
    return [record for row in rows if (record := _row_to_record(row)) is not None]


def create_source_model(  # noqa: PLR0913
    table_name: str,
    *,
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object] | None,
) -> SourceModelRecord:
    table_name = _coerce_table_name(table_name)
    with database_runtime.transaction_sync() as connection:
        if is_default:
            _clear_default_source_model(connection, table_name, source_id=source_id)
        connection.execute(
            f"""
            INSERT INTO {table_name} (
                model_id,
                source_id,
                model_identifier,
                display_name,
                enabled,
                is_default,
                extra_params_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                source_id,
                model_identifier,
                display_name,
                1 if enabled else 0,
                1 if is_default else 0,
                dumps(extra_params or {}, ensure_ascii=False),
                _utcnow_text(),
            ),
        )
    return SourceModelRecord(
        model_id=model_id,
        source_id=source_id,
        model_identifier=model_identifier,
        display_name=display_name,
        enabled=enabled,
        is_default=is_default,
        extra_params=extra_params or {},
    )


def update_source_model(  # noqa: PLR0913
    table_name: str,
    *,
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
    extra_params: dict[str, object] | None,
) -> SourceModelRecord | None:
    table_name = _coerce_table_name(table_name)
    with database_runtime.transaction_sync() as connection:
        existing = connection.execute(
            f"SELECT model_id FROM {table_name} WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        if existing is None:
            return None
        if is_default:
            _clear_default_source_model(connection, table_name, source_id=source_id)
        connection.execute(
            f"""
            UPDATE {table_name}
            SET
                source_id = ?,
                model_identifier = ?,
                display_name = ?,
                enabled = ?,
                is_default = ?,
                extra_params_json = ?,
                updated_at = ?
            WHERE model_id = ?
            """,
            (
                source_id,
                model_identifier,
                display_name,
                1 if enabled else 0,
                1 if is_default else 0,
                dumps(extra_params or {}, ensure_ascii=False),
                _utcnow_text(),
                model_id,
            ),
        )
    return SourceModelRecord(
        model_id=model_id,
        source_id=source_id,
        model_identifier=model_identifier,
        display_name=display_name,
        enabled=enabled,
        is_default=is_default,
        extra_params=extra_params or {},
    )


def delete_source_model(table_name: str, *, model_id: str) -> bool:
    table_name = _coerce_table_name(table_name)
    with database_runtime.connect_sync() as connection:
        cursor = connection.execute(
            f"DELETE FROM {table_name} WHERE model_id = ?",
            (model_id,),
        )
    return cursor.rowcount > 0


def clear_default_source_model(table_name: str, *, source_id: str) -> None:
    table_name = _coerce_table_name(table_name)
    with database_runtime.transaction_sync() as connection:
        _clear_default_source_model(connection, table_name, source_id=source_id)


def _row_to_record(row: tuple[object, ...] | None) -> SourceModelRecord | None:
    if row is None:
        return None
    extra_params = safe_json_loads(
        str(row[6]) if row[6] is not None else None,
        default={},
    )
    return SourceModelRecord(
        model_id=str(row[0]),
        source_id=str(row[1]),
        model_identifier=str(row[2]),
        display_name=str(row[3]),
        enabled=bool(row[4]),
        is_default=bool(row[5]),
        extra_params=extra_params if isinstance(extra_params, dict) else {},
    )


def _clear_default_source_model(
    connection: "Connection",
    table_name: str,
    *,
    source_id: str,
) -> None:
    connection.execute(
        f"""
        UPDATE {table_name}
        SET is_default = 0, updated_at = ?
        WHERE source_id = ?
        """,
        (_utcnow_text(), source_id),
    )


def _coerce_table_name(table_name: str) -> str:
    if table_name not in SOURCE_MODEL_TABLE_NAMES:
        raise UnsupportedSourceModelTableError(table_name)
    return table_name


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
