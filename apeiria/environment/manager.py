"""Operations-plane environment service."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from apeiria.db import ApeiriaDatabase
from apeiria.environment.extension_project import (
    find_uv_executable,
)
from apeiria.environment.models import (
    EnvironmentSnapshot,
    FrontendBuildRunResult,
    FrontendBuildSnapshot,
    FrontendBuildStreamEvent,
    ProjectConfigBootstrapResult,
)
from apeiria.utils.files import _load_toml_module
from apeiria.utils.project_context import current_project_root
from apeiria.webui.frontend_build import (
    frontend_workspace_dir,
    frontend_workspace_name,
    read_frontend_build_status,
    write_frontend_build_meta,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_PLUGIN_PROJECT_RELATIVE_PATH = Path(".apeiria") / "extensions"
_PLUGIN_PROJECT_NAME = "apeiria-user-plugins"
_PYTHON_VERSION_FALLBACK = ">=3.10, <4.0"


def _uv_command_failed_error() -> RuntimeError:
    return RuntimeError("uv command failed")


class EnvironmentService:
    """Host environment operations shared by CLI and HTTP entrypoints."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = (
            project_root.resolve() if project_root is not None else None
        )

    @property
    def project_root(self) -> Path:
        return self._project_root or current_project_root()

    def main_config_path(self) -> Path:
        return self.project_root / "apeiria.config.toml"

    def plugin_project_root(self) -> Path:
        return self.project_root / _PLUGIN_PROJECT_RELATIVE_PATH

    def plugin_project_pyproject_path(self) -> Path:
        return self.plugin_project_root() / "pyproject.toml"

    def plugin_project_lock_path(self) -> Path:
        return self.plugin_project_root() / "uv.lock"

    def plugin_project_exists(self) -> bool:
        return self.plugin_project_pyproject_path().is_file()

    def plugin_project_venv_path(self) -> Path:
        return self.plugin_project_root() / ".venv"

    def uv_cache_dir(self) -> Path:
        return self.project_root / ".apeiria" / "cache" / "uv"

    def _main_requires_python(self) -> str:
        pyproject_path = self.project_root / "pyproject.toml"
        toml_module = _load_toml_module()
        if toml_module is None:
            return _PYTHON_VERSION_FALLBACK
        try:
            with pyproject_path.open("rb") as file:
                data = toml_module.load(file)
        except (OSError, ValueError):
            return _PYTHON_VERSION_FALLBACK

        project = data.get("project")
        if not isinstance(project, dict):
            return _PYTHON_VERSION_FALLBACK
        requires_python = project.get("requires-python")
        if not isinstance(requires_python, str) or not requires_python.strip():
            return _PYTHON_VERSION_FALLBACK
        return requires_python.strip()

    def _plugin_project_template(self) -> str:
        requires_python = self._main_requires_python()
        return "\n".join(
            [
                "[project]",
                f'name = "{_PLUGIN_PROJECT_NAME}"',
                'version = "0.0.0"',
                f'requires-python = "{requires_python}"',
                "dependencies = []",
                "",
                "[tool.uv]",
                "package = false",
                "",
            ]
        )

    def ensure_plugin_project(self) -> Path:
        root = self.plugin_project_root()
        root.mkdir(parents=True, exist_ok=True)
        pyproject_path = self.plugin_project_pyproject_path()
        if not pyproject_path.exists():
            pyproject_path.write_text(self._plugin_project_template(), encoding="utf-8")
        return root

    def get_environment_snapshot(self) -> EnvironmentSnapshot:
        root = self.project_root
        frontend_dir = frontend_workspace_dir(root)
        build_status = read_frontend_build_status(root)
        build_tool = shutil.which("pnpm") or shutil.which("npm")
        return EnvironmentSnapshot(
            project_root=root,
            main_config_path=self.main_config_path(),
            plugin_project_root=self.plugin_project_root(),
            main_lock_exists=(root / "uv.lock").exists(),
            plugin_project_exists=self.plugin_project_exists(),
            plugin_lock_exists=self.plugin_project_lock_path().exists(),
            project_config_exists=self.main_config_path().exists(),
            plugin_config_exists=(root / "apeiria.plugins.toml").exists(),
            adapter_config_exists=(root / "apeiria.adapters.toml").exists(),
            driver_config_exists=(root / "apeiria.drivers.toml").exists(),
            main_virtualenv_exists=(root / ".venv").is_dir(),
            uv_available=shutil.which("uv") is not None,
            node_available=shutil.which("node") is not None,
            pnpm_available=shutil.which("pnpm") is not None,
            npm_available=shutil.which("npm") is not None,
            frontend_workspace_name=frontend_workspace_name(root),
            frontend_workspace_exists=(frontend_dir / "package.json").is_file(),
            frontend_dist_exists=(frontend_dir / "dist").is_dir(),
            frontend_build_is_built=build_status.is_built,
            frontend_build_is_stale=build_status.is_stale,
            frontend_build_detail=build_status.detail,
            frontend_build_tool=Path(build_tool).name if build_tool else None,
        )

    def ensure_runtime_env_files(self) -> None:
        for target in (
            self.project_root / ".env",
            self.project_root / ".env.dev",
            self.project_root / ".env.prod",
        ):
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

    def _project_config_templates(self) -> tuple[tuple[Path, Path], ...]:
        return (
            (
                self.project_root / "apeiria.config.example.toml",
                self.project_root / "apeiria.config.toml",
            ),
            (
                self.project_root / "apeiria.plugins.example.toml",
                self.project_root / "apeiria.plugins.toml",
            ),
            (
                self.project_root / "apeiria.adapters.example.toml",
                self.project_root / "apeiria.adapters.toml",
            ),
            (
                self.project_root / "apeiria.drivers.example.toml",
                self.project_root / "apeiria.drivers.toml",
            ),
        )

    def ensure_project_config_files(self) -> ProjectConfigBootstrapResult:
        created: list[str] = []
        skipped: list[str] = []

        for source, destination in self._project_config_templates():
            if destination.exists():
                skipped.append(destination.name)
                continue
            if not source.exists():
                msg = f"missing config template: {source.name}"
                raise RuntimeError(msg)

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            created.append(destination.name)

        return ProjectConfigBootstrapResult(created=created, skipped=skipped)

    def run_uv_for_main_project(self, *args: str) -> None:
        executable = find_uv_executable()
        cache_dir = self.uv_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["UV_CACHE_DIR"] = str(cache_dir)
        env["UV_PROJECT_ENVIRONMENT"] = str(self.project_root / ".venv")
        env.pop("VIRTUAL_ENV", None)
        result = subprocess.run(
            [executable, *args],
            cwd=self.project_root,
            check=False,
            env=env,
        )
        if result.returncode != 0:
            raise _uv_command_failed_error()

    def _run_uv_for_directory(self, cwd: Path, *args: str) -> None:
        executable = find_uv_executable()
        cache_dir = self.uv_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["UV_CACHE_DIR"] = str(cache_dir)
        env["UV_PROJECT_ENVIRONMENT"] = str(cwd / ".venv")
        env.pop("VIRTUAL_ENV", None)
        result = subprocess.run(
            [executable, *args],
            cwd=cwd,
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            output_parts = [
                part.strip()
                for part in (result.stdout, result.stderr)
                if part and part.strip()
            ]
            output = "\n".join(output_parts)
            msg = f"uv command failed: {' '.join(args)}"
            if output:
                msg = f"{msg}\n{output}"
            raise RuntimeError(msg)

    def sync_plugin_project(self, *, locked: bool = True) -> Path:
        root = self.ensure_plugin_project()
        args = ["sync"]
        if locked and self.plugin_project_lock_path().exists():
            args.append("--locked")
        self._run_uv_for_directory(root, *args)
        return root

    def sync_main_project(self, *, no_dev: bool = False) -> None:
        args = ["sync"]
        if (self.project_root / "uv.lock").exists():
            args.append("--locked")
        if no_dev:
            args.append("--no-dev")
        self.run_uv_for_main_project(*args)

    def initialize_user_environment(
        self,
        *,
        no_dev: bool = False,
    ) -> ProjectConfigBootstrapResult:
        result = self.ensure_project_config_files()
        self.ensure_runtime_env_files()
        self.sync_main_project(no_dev=no_dev)
        self.ensure_plugin_project()
        self.sync_plugin_project(locked=True)
        return result

    def repair_user_environment(self) -> ProjectConfigBootstrapResult:
        return self.initialize_user_environment()

    def validate_database_schema(self) -> None:
        database = ApeiriaDatabase(project_root=self.project_root)
        database.ensure_ready()

    def repair_database_schema(self) -> None:
        self.validate_database_schema()

    def runtime_export_targets(self) -> list[tuple[Path, Path]]:
        database_path = ApeiriaDatabase(project_root=self.project_root).database_path()
        return [
            (self.main_config_path(), Path("apeiria.config.toml")),
            (self.project_root / "apeiria.plugins.toml", Path("apeiria.plugins.toml")),
            (
                self.project_root / "apeiria.adapters.toml",
                Path("apeiria.adapters.toml"),
            ),
            (
                self.project_root / "apeiria.drivers.toml",
                Path("apeiria.drivers.toml"),
            ),
            (
                self.plugin_project_pyproject_path(),
                Path(".apeiria/extensions/pyproject.toml"),
            ),
            (
                self.plugin_project_lock_path(),
                Path(".apeiria/extensions/uv.lock"),
            ),
            (
                database_path,
                Path("data/db/apeiria.sqlite3"),
            ),
        ]

    def _database_path(self) -> Path:
        return ApeiriaDatabase(project_root=self.project_root).database_path()

    def _copy_runtime_export_target(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source == self._database_path():
            source_connection = sqlite3.connect(source)
            destination_connection = sqlite3.connect(destination)
            try:
                source_connection.backup(destination_connection)
            finally:
                destination_connection.close()
                source_connection.close()
            shutil.copystat(source, destination)
            return
        shutil.copy2(source, destination)

    def export_runtime_state(self, output_dir: Path | None = None) -> tuple[Path, int]:
        target_root = (
            output_dir.expanduser().resolve()
            if output_dir is not None
            else (self.project_root / ".apeiria" / "export").resolve()
        )
        copied = 0
        for source, relative_path in self.runtime_export_targets():
            if not source.exists():
                continue
            destination = target_root / relative_path
            self._copy_runtime_export_target(source, destination)
            copied += 1
        return target_root, copied

    def import_runtime_state(self, input_dir: Path) -> tuple[Path, int]:
        source_root = input_dir.expanduser().resolve()
        if not source_root.is_dir():
            msg = f"import source not found: {source_root}"
            raise FileNotFoundError(msg)

        copied = 0
        for destination, relative_path in self.runtime_export_targets():
            source = source_root / relative_path
            if not source.exists():
                if destination == self._database_path():
                    continue
                if destination.exists():
                    destination.unlink()
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1

        self.initialize_user_environment()
        return source_root, copied

    def get_frontend_build_status(self) -> FrontendBuildSnapshot:
        snapshot = self.get_environment_snapshot()
        return FrontendBuildSnapshot(
            is_built=snapshot.frontend_build_is_built,
            is_stale=snapshot.frontend_build_is_stale,
            can_build=snapshot.frontend_workspace_exists
            and snapshot.frontend_build_tool is not None,
            build_tool=snapshot.frontend_build_tool,
            detail=snapshot.frontend_build_detail,
        )

    def build_frontend_sync(self) -> FrontendBuildRunResult:
        return asyncio.run(self.rebuild_frontend())

    async def rebuild_frontend(self) -> FrontendBuildRunResult:
        status = self.get_frontend_build_status()
        if not status.can_build or status.build_tool is None:
            raise RuntimeError("build_tool_unavailable")

        command = (
            ["pnpm", "build"]
            if status.build_tool == "pnpm"
            else ["npm", "run", "build"]
        )
        frontend_dir = frontend_workspace_dir(self.project_root)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(frontend_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        logs = self._merge_build_logs(
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
        if process.returncode != 0:
            raise RuntimeError(logs.strip() or "build_failed")

        write_frontend_build_meta(self.project_root)
        next_status = self.get_frontend_build_status()
        return FrontendBuildRunResult(
            is_built=next_status.is_built,
            is_stale=next_status.is_stale,
            can_build=next_status.can_build,
            build_tool=next_status.build_tool,
            detail=next_status.detail,
            logs=logs,
        )

    async def stream_frontend_rebuild(self) -> AsyncIterator[bytes]:
        status = self.get_frontend_build_status()
        if not status.can_build or status.build_tool is None:
            raise RuntimeError("build_tool_unavailable")

        command = (
            ["pnpm", "build"]
            if status.build_tool == "pnpm"
            else ["npm", "run", "build"]
        )
        frontend_dir = frontend_workspace_dir(self.project_root)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(frontend_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        output_chunks: list[str] = []
        assert process.stdout is not None
        while True:
            chunk = await process.stdout.read(1024)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            output_chunks.append(text)
            yield self._encode_build_stream_event(
                FrontendBuildStreamEvent(event="chunk", chunk=text)
            )

        return_code = await process.wait()
        logs = "".join(output_chunks).strip()
        if return_code != 0:
            yield self._encode_build_stream_event(
                FrontendBuildStreamEvent(
                    event="error",
                    detail=logs or "build_failed",
                )
            )
            return

        write_frontend_build_meta(self.project_root)
        next_status = self.get_frontend_build_status()
        yield self._encode_build_stream_event(
            FrontendBuildStreamEvent(event="done", status=next_status)
        )

    def _merge_build_logs(self, stdout: str, stderr: str) -> str:
        sections: list[str] = []
        if stdout.strip():
            sections.append(stdout.strip())
        if stderr.strip():
            sections.append(stderr.strip())
        return "\n\n".join(sections)

    def _encode_build_stream_event(self, event: FrontendBuildStreamEvent) -> bytes:
        payload: dict[str, object] = {"event": event.event}
        if event.chunk:
            payload["chunk"] = event.chunk
        if event.detail is not None:
            payload["detail"] = event.detail
        if event.status is not None:
            payload["status"] = {
                "is_built": event.status.is_built,
                "is_stale": event.status.is_stale,
                "can_build": event.status.can_build,
                "build_tool": event.status.build_tool,
                "detail": event.status.detail,
            }
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


environment_service = EnvironmentService()
