from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from apeiria.db import CURRENT_SCHEMA_LINE, CURRENT_SCHEMA_VERSION
from apeiria.db.runtime import ApeiriaDatabase
from apeiria.environment.frontend_build import (
    build_meta_path,
    compute_frontend_fingerprint,
    read_frontend_build_status,
    write_frontend_build_meta,
)
from apeiria.environment.health import HealthService
from apeiria.environment.manager import EnvironmentService

if TYPE_CHECKING:
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


def test_webui_build_health_reports_current_metadata(tmp_path: Path) -> None:
    _create_frontend_fixture(tmp_path)
    write_frontend_build_meta(tmp_path)

    snapshot = HealthService(EnvironmentService(project_root=tmp_path)).get_snapshot()

    check = _health_check(snapshot, "frontend_build")
    assert check.ok is True
    assert check.detail == "current"


def test_webui_build_health_warns_when_metadata_is_missing(tmp_path: Path) -> None:
    _create_frontend_fixture(tmp_path)

    snapshot = HealthService(EnvironmentService(project_root=tmp_path)).get_snapshot()

    check = _health_check(snapshot, "frontend_build")
    assert check.ok is False
    assert check.detail == "build_meta_missing"
    assert check.hint == "Rebuild the frontend once to refresh build metadata."


def test_webui_build_metadata_entrypoint_refreshes_stale_metadata(
    tmp_path: Path,
) -> None:
    _create_frontend_fixture(tmp_path)
    write_frontend_build_meta(tmp_path)
    (tmp_path / "web" / "src" / "main.ts").write_text(
        "console.log('changed')\n",
        encoding="utf-8",
    )
    assert read_frontend_build_status(tmp_path).detail == "stale"

    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "write-webui-build-meta.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
        ],
        check=True,
    )

    meta = json.loads(build_meta_path(tmp_path).read_text(encoding="utf-8"))
    assert meta["fingerprint"] == compute_frontend_fingerprint(tmp_path)
    assert read_frontend_build_status(tmp_path).detail == "current"


def test_web_package_build_runs_metadata_writer() -> None:
    package_path = Path(__file__).resolve().parents[2] / "web" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))

    assert "write-build-meta" in package["scripts"]
    assert "write-build-meta" in package["scripts"]["build"]


def _create_frontend_fixture(project_root: Path) -> None:
    web = project_root / "web"
    (web / "src").mkdir(parents=True)
    (web / "dist").mkdir(parents=True)
    (web / "package.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
    (web / "index.html").write_text("<main></main>\n", encoding="utf-8")
    (web / "src" / "main.ts").write_text("console.log('ready')\n", encoding="utf-8")
    (web / "dist" / "index.html").write_text("<main></main>\n", encoding="utf-8")
