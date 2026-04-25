"""Operations-plane health service."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from apeiria.db import (
    CURRENT_SCHEMA_LINE,
    CURRENT_SCHEMA_VERSION,
    ApeiriaDatabase,
)
from apeiria.environment.manager import (
    EnvironmentService,
    environment_service,
)
from apeiria.environment.models import HealthCheck, HealthSnapshot

if TYPE_CHECKING:
    from pathlib import Path

_CHECK_MESSAGES: dict[tuple[str, str], tuple[str, str | None]] = {
    ("uv", "available"): ("uv is available.", None),
    ("uv", "missing"): (
        "uv is not installed.",
        "Install uv, then run `apeiria env init`.",
    ),
    ("main_config", "present"): ("Project config file is present.", None),
    ("main_config", "missing"): (
        "Missing `apeiria.config.toml`.",
        "Run `apeiria env init`.",
    ),
    ("plugin_config", "present"): ("Plugin config file is present.", None),
    ("plugin_config", "missing"): (
        "Missing `apeiria.plugins.toml`.",
        "Run `apeiria env init`.",
    ),
    ("adapter_config", "present"): ("Adapter config file is present.", None),
    ("adapter_config", "missing"): (
        "Missing `apeiria.adapters.toml`.",
        "Run `apeiria env init`.",
    ),
    ("driver_config", "present"): ("Driver config file is present.", None),
    ("driver_config", "missing"): (
        "Missing `apeiria.drivers.toml`.",
        "Run `apeiria env init`.",
    ),
    ("main_venv", "present"): ("Main Python environment is present.", None),
    ("main_venv", "missing"): (
        "Main project virtual environment is missing.",
        "Run `uv sync --locked` or `apeiria env init`.",
    ),
    ("extension_project", "present"): (
        "Extension environment project is present.",
        None,
    ),
    ("extension_project", "missing"): (
        "Managed extension project is missing.",
        "Run `apeiria env init` to create `.apeiria/extensions`.",
    ),
    ("database", "missing"): (
        "Apeiria database has not been initialized yet.",
        "Run `apeiria check` or start Apeiria once to create it.",
    ),
    ("database", "current"): ("Apeiria database schema is current.", None),
    ("database", "unsupported"): (
        "Apeiria database schema version is not supported by this build.",
        "Move the current local database aside, then run `apeiria check` "
        "to recreate it.",
    ),
    ("database", "incompatible"): (
        "Apeiria database schema is incompatible.",
        "Restore a compatible database backup or move the current database aside.",
    ),
    ("database", "unreadable"): (
        "Apeiria database cannot be read.",
        "Check file permissions or restore a valid database backup.",
    ),
    ("frontend_workspace", "present"): ("Frontend workspace is present.", None),
    ("frontend_workspace", "missing"): (
        "Frontend workspace is missing.",
        "Restore the selected frontend workspace if you need the Web UI.",
    ),
    ("frontend_toolchain", "missing"): (
        "No frontend package manager was found.",
        "Install pnpm or npm to rebuild Web UI assets.",
    ),
    ("frontend_build", "current"): ("Web UI build artifacts are up to date.", None),
    ("frontend_build", "dist_missing"): (
        "Web UI build artifacts are missing.",
        "Run `apeiria run --build` or build the selected frontend workspace.",
    ),
    ("frontend_build", "build_meta_missing"): (
        "Web UI build metadata is missing.",
        "Rebuild the frontend once to refresh build metadata.",
    ),
    ("frontend_build", "fingerprint_missing"): (
        "Web UI build fingerprint is missing.",
        "Rebuild the frontend once to restore build metadata.",
    ),
    ("frontend_build", "stale"): (
        "Web UI build artifacts are outdated.",
        "Run `apeiria run --build` before using the Web UI.",
    ),
}


class HealthService:
    """Inspect the local workspace without mutating it."""

    def __init__(
        self,
        environment: EnvironmentService | None = None,
    ) -> None:
        self._environment = environment or environment_service

    def get_snapshot(self) -> HealthSnapshot:
        environment = self._environment.get_environment_snapshot()
        frontend_toolchain = environment.frontend_build_tool or "missing"
        checks = [
            self._build_check(
                key="uv",
                ok=environment.uv_available,
                detail="available" if environment.uv_available else "missing",
            ),
            self._build_check(
                key="main_config",
                ok=environment.project_config_exists,
                detail="present" if environment.project_config_exists else "missing",
            ),
            self._build_check(
                key="plugin_config",
                ok=environment.plugin_config_exists,
                detail="present" if environment.plugin_config_exists else "missing",
            ),
            self._build_check(
                key="adapter_config",
                ok=environment.adapter_config_exists,
                detail="present" if environment.adapter_config_exists else "missing",
            ),
            self._build_check(
                key="driver_config",
                ok=environment.driver_config_exists,
                detail="present" if environment.driver_config_exists else "missing",
            ),
            self._build_check(
                key="main_venv",
                ok=environment.main_virtualenv_exists,
                detail="present" if environment.main_virtualenv_exists else "missing",
            ),
            self._build_check(
                key="extension_project",
                ok=environment.plugin_project_exists,
                detail="present" if environment.plugin_project_exists else "missing",
            ),
            self._build_database_check(),
            self._build_check(
                key="frontend_workspace",
                ok=environment.frontend_workspace_exists,
                detail="present"
                if environment.frontend_workspace_exists
                else "missing",
            ),
            self._build_check(
                key="frontend_toolchain",
                ok=(
                    not environment.frontend_workspace_exists
                    or environment.frontend_build_tool is not None
                ),
                detail=frontend_toolchain,
            ),
            self._build_check(
                key="frontend_build",
                ok=(
                    environment.frontend_build_is_built
                    and not environment.frontend_build_is_stale
                ),
                detail=environment.frontend_build_detail or "unknown",
            ),
        ]
        status = "ok" if all(check.ok for check in checks) else "warning"
        return HealthSnapshot(
            status=status,
            project_root=environment.project_root,
            checks=checks,
            environment=environment,
        )

    def _build_check(
        self,
        *,
        key: str,
        ok: bool,
        detail: str,
    ) -> HealthCheck:
        message, hint = self._describe_check(key=key, ok=ok, detail=detail)
        return HealthCheck(
            key=key,
            ok=ok,
            detail=detail,
            message=message,
            hint=hint,
        )

    def _describe_check(
        self,
        *,
        key: str,
        ok: bool,
        detail: str,
    ) -> tuple[str, str | None]:
        if key == "frontend_toolchain" and ok:
            return (f"Frontend build tool is available: {detail}.", None)
        if message := _CHECK_MESSAGES.get((key, detail)):
            return message
        return (f"Check `{key}` is {detail}.", None)

    def _build_database_check(self) -> HealthCheck:
        database = ApeiriaDatabase(project_root=self._environment.project_root)
        database_path = database.database_path()
        if not database_path.exists():
            detail = "missing"
            ok = True
        else:
            detail, ok = self._inspect_database_schema(database_path)
        return self._build_check(key="database", ok=ok, detail=detail)

    def _inspect_database_schema(self, database_path: "Path") -> tuple[str, bool]:
        try:
            connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
            try:
                row = connection.execute(
                    """
                    SELECT schema_line, schema_version
                    FROM apeiria_schema_meta
                    WHERE id = 1
                    """
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                detail = "incompatible"
            else:
                detail = "unreadable"
            ok = False
        except sqlite3.DatabaseError:
            detail = "unreadable"
            ok = False
        else:
            detail, ok = self._classify_database_schema_row(row)
        return detail, ok

    @staticmethod
    def _classify_database_schema_row(row: object | None) -> tuple[str, bool]:
        detail = "current"
        ok = True
        if row is None:
            return "incompatible", False
        try:
            schema_line = str(row[0])  # type: ignore[index]
            schema_version = int(row[1])  # type: ignore[index]
        except (IndexError, TypeError, ValueError):
            detail = "incompatible"
            ok = False
        else:
            if schema_line != CURRENT_SCHEMA_LINE:
                detail = "incompatible"
                ok = False
            elif schema_version != CURRENT_SCHEMA_VERSION:
                detail = "unsupported"
                ok = False
        return detail, ok


health_service = HealthService()
