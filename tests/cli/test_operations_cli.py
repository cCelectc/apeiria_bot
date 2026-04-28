from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from apeiria.app.plugins.store.sources import _read_package_requirement
from apeiria.cli.main import cli
from apeiria.cli.support import store_package_dependency
from apeiria.db.runtime import ApeiriaDatabase
from apeiria.utils.project_context import default_project_root

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class _StorePackage:
    project_link: str
    module_name: str = "nonebot_plugin_demo"

    def as_dependency(self) -> str:
        return "nonebot-plugin-demo>=1.0"


def _write_plugin_config(project_root: Path) -> None:
    (project_root / "apeiria.plugins.toml").write_text(
        "\n".join(
            [
                "[plugins]",
                'modules = ["nonebot_plugin_demo"]',
                'dirs = ["local_plugins"]',
                "",
                "[plugin_packages]",
                '"nonebot-plugin-demo" = ["nonebot_plugin_demo"]',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_adapter_config(project_root: Path) -> None:
    (project_root / "apeiria.adapters.toml").write_text(
        "\n".join(
            [
                "[adapters]",
                'modules = ["nonebot.adapters.demo"]',
                "",
                "[adapter_packages]",
                '"nonebot-adapter-demo" = ["nonebot.adapters.demo"]',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_driver_config(project_root: Path) -> None:
    (project_root / "apeiria.drivers.toml").write_text(
        "\n".join(
            [
                "[drivers]",
                'builtin = ["~demo"]',
                "",
                "[driver_packages]",
                '"nonebot-driver-demo" = ["~demo"]',
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_status_json_preserves_default_project_root() -> None:
    result = CliRunner().invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["project_root"] == str(default_project_root())


def test_status_json_uses_selected_project_root(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--cwd", str(tmp_path), "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["environment"]["main_config_path"] == str(
        tmp_path.resolve() / "apeiria.config.toml"
    )
    assert {check["key"] for check in payload["checks"]} >= {
        "main_config",
        "plugin_config",
        "database",
    }


def test_env_info_json_and_text_outputs(tmp_path: Path) -> None:
    runner = CliRunner()

    json_result = runner.invoke(cli, ["--cwd", str(tmp_path), "env", "info", "--json"])
    text_result = runner.invoke(cli, ["--cwd", str(tmp_path), "env", "info"])

    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["plugin_project_root"] == str(
        tmp_path.resolve() / ".apeiria" / "extensions"
    )
    assert text_result.exit_code == 0
    assert "project_root=" in text_result.output
    assert "--json" not in text_result.output


def test_env_doctor_json_outputs_health_snapshot(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli,
        ["--cwd", str(tmp_path), "env", "doctor", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["project_root"] == str(tmp_path.resolve())
    assert isinstance(payload["checks"], list)


def test_plugin_registered_json_reads_selected_project_root(tmp_path: Path) -> None:
    _write_plugin_config(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["--cwd", str(tmp_path), "plugin", "list", "--registered", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["resource"] == "plugin"
    assert payload["mode"] == "registered"
    assert payload["config"] == str(tmp_path.resolve() / "apeiria.plugins.toml")
    assert payload["modules"] == ["nonebot_plugin_demo"]
    assert payload["dirs"] == ["local_plugins"]


def test_adapter_and_driver_registered_json_reads_selected_project_root(
    tmp_path: Path,
) -> None:
    _write_adapter_config(tmp_path)
    _write_driver_config(tmp_path)
    runner = CliRunner()

    adapter_result = runner.invoke(
        cli,
        ["--cwd", str(tmp_path), "adapter", "list", "--registered", "--json"],
    )
    driver_result = runner.invoke(
        cli,
        ["--cwd", str(tmp_path), "driver", "list", "--registered", "--json"],
    )

    assert adapter_result.exit_code == 0
    assert json.loads(adapter_result.output)["modules"] == ["nonebot.adapters.demo"]
    assert driver_result.exit_code == 0
    assert json.loads(driver_result.output)["builtin"] == ["~demo"]


def test_resource_search_json_uses_requested_mode(tmp_path: Path) -> None:
    _write_plugin_config(tmp_path)

    result = CliRunner().invoke(
        cli,
        [
            "--cwd",
            str(tmp_path),
            "plugin",
            "search",
            "demo",
            "--registered",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "registered"
    assert payload["modules"] == ["nonebot_plugin_demo"]


def test_resource_installed_json_reports_package_bindings(tmp_path: Path) -> None:
    _write_plugin_config(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["--cwd", str(tmp_path), "plugin", "list", "--installed", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "installed"
    assert payload["packages"] == [
        {"name": "nonebot-plugin-demo", "modules": ["nonebot_plugin_demo"]}
    ]


def test_resource_store_json_reports_store_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _StorePackage(project_link="https://example.test/demo.git")

    def fake_store_packages_cli(*_args: object, **_kwargs: object) -> list[object]:
        return [package]

    monkeypatch.setattr(
        "apeiria.cli.commands.plugin.store_packages_cli",
        fake_store_packages_cli,
    )

    result = CliRunner().invoke(cli, ["plugin", "list", "--store", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "store"
    assert payload["items"][0]["package_requirement"] == package.project_link


def test_plugin_text_output_remains_human_readable(tmp_path: Path) -> None:
    _write_plugin_config(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["--cwd", str(tmp_path), "plugin", "list", "--registered"],
    )

    assert result.exit_code == 0
    assert "nonebot_plugin_demo" in result.output
    assert not result.output.lstrip().startswith("{")


def test_run_uses_custom_entry_and_forwards_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_run(
        args: list[str],
        *,
        cwd: Path,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is False
        calls.append((args, cwd))
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("apeiria.cli.commands.env.subprocess.run", fake_run)

    result = CliRunner().invoke(
        cli,
        [
            "--cwd",
            str(tmp_path),
            "run",
            "--entry",
            "user_bot.py",
            "--",
            "--verbose",
        ],
    )

    assert result.exit_code == 0
    assert calls == [([sys.executable, "user_bot.py", "--verbose"], tmp_path.resolve())]


def test_run_reload_uses_apeiria_wrapper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, str, tuple[str, ...]]] = []

    def fake_reload(
        *,
        cwd: Path,
        entry_file: str,
        extra_args: tuple[str, ...],
    ) -> int:
        calls.append((cwd, entry_file, extra_args))
        return 0

    monkeypatch.setattr("apeiria.cli.commands.env.run_with_reload", fake_reload)

    result = CliRunner().invoke(
        cli,
        ["--cwd", str(tmp_path), "run", "--reload", "--entry", "dev_bot.py"],
    )

    assert result.exit_code == 0
    assert calls == [(tmp_path.resolve(), "dev_bot.py", ())]


def test_resource_search_commands_are_visible() -> None:
    runner = CliRunner()

    for command_name in ("plugin", "adapter", "driver"):
        result = runner.invoke(cli, [command_name, "--help"])
        assert result.exit_code == 0
        assert "search" in result.output


@pytest.mark.parametrize(
    ("resource", "binding_option", "install_path", "uninstall_path"),
    [
        (
            "plugin",
            "--module",
            "apeiria.cli.commands.plugin.install_resource_requirement",
            "apeiria.cli.commands.plugin.uninstall_resource_requirement",
        ),
        (
            "adapter",
            "--module",
            "apeiria.cli.commands.adapter.install_resource_requirement",
            "apeiria.cli.commands.adapter.uninstall_resource_requirement",
        ),
        (
            "driver",
            "--builtin",
            "apeiria.cli.commands.driver.install_resource_requirement",
            "apeiria.cli.commands.driver.uninstall_resource_requirement",
        ),
    ],
)
def test_add_and_remove_aliases_route_to_package_operations(
    monkeypatch: pytest.MonkeyPatch,
    resource: str,
    binding_option: str,
    install_path: str,
    uninstall_path: str,
) -> None:
    calls: list[tuple[str, str, tuple[object, ...]]] = []

    def fake_install(*args: object, **_kwargs: object) -> str:
        calls.append(("install", str(args[1]), args))
        return "demo-package"

    def fake_uninstall(*args: object, **_kwargs: object) -> str:
        calls.append(("uninstall", str(args[1]), args))
        return "demo-package"

    monkeypatch.setattr(install_path, fake_install)
    monkeypatch.setattr(uninstall_path, fake_uninstall)

    runner = CliRunner()
    add_result = runner.invoke(
        cli,
        [
            resource,
            "add",
            "--requirement",
            "demo-package",
            binding_option,
            "demo",
        ],
    )
    remove_result = runner.invoke(
        cli,
        [resource, "remove", "demo-package", binding_option, "demo"],
    )

    assert add_result.exit_code == 0
    assert remove_result.exit_code == 0
    assert [call[0] for call in calls] == ["install", "uninstall"]


@pytest.mark.parametrize("resource", ["plugin", "adapter", "driver"])
def test_cli_store_requirement_matches_webui_candidate_resolution(
    resource: str,
) -> None:
    assert resource in {"plugin", "adapter", "driver"}
    package = _StorePackage(project_link="https://example.test/demo.git")

    assert store_package_dependency(package, None) == _read_package_requirement(package)


def test_db_status_json_reports_missing_database(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["--cwd", str(tmp_path), "db", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["path"] == str(
        tmp_path.resolve() / "data" / "db" / "apeiria.sqlite3"
    )
    assert payload["exists"] is False
    assert payload["schema"]["status"] == "missing"


def test_db_check_is_non_mutating_and_fails_when_database_is_missing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "db" / "apeiria.sqlite3"

    result = CliRunner().invoke(cli, ["--cwd", str(tmp_path), "db", "check", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["ready"] is False
    assert payload["schema"]["status"] == "missing"
    assert not database_path.exists()


def test_db_repair_creates_ready_database(tmp_path: Path) -> None:
    runner = CliRunner()

    repair_result = runner.invoke(cli, ["--cwd", str(tmp_path), "db", "repair"])
    check_result = runner.invoke(cli, ["--cwd", str(tmp_path), "db", "check", "--json"])

    assert repair_result.exit_code == 0
    assert "repaired database" in repair_result.output
    assert check_result.exit_code == 0
    assert json.loads(check_result.output)["ready"] is True
    assert ApeiriaDatabase(project_root=tmp_path).database_path().is_file()


def test_webui_accounts_command_uses_selected_project_root(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli,
        ["--cwd", str(tmp_path), "webui", "accounts", "list"],
    )

    assert result.exit_code == 0
    assert (tmp_path / "data" / "web_ui" / "secret.json").is_file()
