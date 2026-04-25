from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.db import CURRENT_SCHEMA_LINE, CURRENT_SCHEMA_VERSION
from apeiria.db.runtime import ApeiriaDatabase
from apeiria.environment.health import HealthService
from apeiria.environment.manager import EnvironmentService

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.environment.models import HealthCheck, HealthSnapshot


def _health_check(snapshot: "HealthSnapshot", key: str) -> "HealthCheck":
    for check in snapshot.checks:
        if check.key == key:
            return check
    raise AssertionError(key)


def test_health_reports_missing_database_without_creating_it(tmp_path: Path) -> None:
    service = EnvironmentService(project_root=tmp_path)
    database_path = ApeiriaDatabase(project_root=tmp_path).database_path()

    snapshot = HealthService(service).get_snapshot()

    check = _health_check(snapshot, "database")
    assert check.ok is True
    assert check.detail == "missing"
    assert not database_path.exists()


def test_health_reports_current_database(tmp_path: Path) -> None:
    service = EnvironmentService(project_root=tmp_path)
    ApeiriaDatabase(project_root=tmp_path).ensure_ready()

    snapshot = HealthService(service).get_snapshot()

    check = _health_check(snapshot, "database")
    assert check.ok is True
    assert check.detail == "current"


def test_health_warns_about_unsupported_database_version(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    with database.connect_sync() as connection:
        connection.execute(
            """
            CREATE TABLE apeiria_schema_meta (
                id INTEGER PRIMARY KEY,
                schema_line TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO apeiria_schema_meta (
                id,
                schema_line,
                schema_version,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                CURRENT_SCHEMA_LINE,
                CURRENT_SCHEMA_VERSION + 1,
                "2026-04-25T00:00:00",
                "2026-04-25T00:00:00",
            ),
        )

    snapshot = HealthService(EnvironmentService(project_root=tmp_path)).get_snapshot()

    check = _health_check(snapshot, "database")
    assert check.ok is False
    assert check.detail == "unsupported"
