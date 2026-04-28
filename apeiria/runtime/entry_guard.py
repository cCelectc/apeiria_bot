"""Pre-bootstrap environment diagnostics for bot entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.environment.health import HealthService
from apeiria.environment.manager import EnvironmentService
from apeiria.utils.project_context import current_project_root

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.environment.models import HealthCheck

_CONFIG_CHECK_KEYS = (
    "main_config",
    "plugin_config",
    "adapter_config",
    "driver_config",
)
_BLOCKING_DATABASE_DETAILS = frozenset({"unsupported", "incompatible", "unreadable"})


@dataclass(frozen=True)
class EntryEnvironmentIssue:
    """One startup-blocking environment issue and its smallest next step."""

    key: str
    message: str
    command: str


@dataclass(frozen=True)
class EntryEnvironmentReport:
    """Environment readiness result for a bot entrypoint."""

    project_root: Path
    issues: tuple[EntryEnvironmentIssue, ...]

    @property
    def ready(self) -> bool:
        return not self.issues


class EntryEnvironmentError(RuntimeError):
    """Raised when startup should stop with environment maintenance guidance."""

    def __init__(self, report: EntryEnvironmentReport) -> None:
        self.report = report
        super().__init__(format_entry_environment_error(report))


def inspect_entry_environment(
    project_root: Path | None = None,
) -> EntryEnvironmentReport:
    """Inspect startup prerequisites without mutating project state."""
    root = (
        project_root.resolve() if project_root is not None else current_project_root()
    )
    service = EnvironmentService(project_root=root)
    snapshot = HealthService(service).get_snapshot()
    checks = {check.key: check for check in snapshot.checks}
    issues: list[EntryEnvironmentIssue] = []

    missing_config_checks = [
        check
        for key in _CONFIG_CHECK_KEYS
        if (check := checks.get(key)) is not None and not check.ok
    ]
    if missing_config_checks:
        issues.append(_missing_config_issue(missing_config_checks))

    main_venv = checks.get("main_venv")
    if not missing_config_checks and main_venv is not None and not main_venv.ok:
        issues.append(
            EntryEnvironmentIssue(
                key="main_venv",
                message=main_venv.message,
                command="apeiria env init",
            )
        )

    extension_project = checks.get("extension_project")
    if (
        not missing_config_checks
        and extension_project is not None
        and not extension_project.ok
    ):
        issues.append(
            EntryEnvironmentIssue(
                key="extension_project",
                message=extension_project.message,
                command="apeiria env repair",
            )
        )

    database = checks.get("database")
    if database is not None and database.detail in _BLOCKING_DATABASE_DETAILS:
        issues.append(
            EntryEnvironmentIssue(
                key="database",
                message=database.message,
                command="apeiria db repair",
            )
        )

    return EntryEnvironmentReport(
        project_root=snapshot.project_root,
        issues=tuple(_deduplicate_issues(issues)),
    )


def ensure_entry_environment_ready(project_root: Path | None = None) -> None:
    """Raise user-facing maintenance guidance when startup should not proceed."""
    report = inspect_entry_environment(project_root=project_root)
    if report.ready:
        return
    raise EntryEnvironmentError(report)


def format_entry_environment_error(report: EntryEnvironmentReport) -> str:
    """Format concise terminal guidance for blocked startup."""
    lines = [
        "Apeiria startup environment check failed.",
        f"project: {report.project_root}",
        "",
    ]
    for issue in report.issues:
        lines.append(f"- {issue.message}")
        if issue.key == "database":
            lines.append("  inspect: `apeiria db check`")
        lines.append(f"  next step: `{issue.command}`")
    return "\n".join(lines)


def _missing_config_issue(
    checks: list["HealthCheck"],
) -> EntryEnvironmentIssue:
    names = ", ".join(_config_filename(check.key) for check in checks)
    return EntryEnvironmentIssue(
        key="config",
        message=(
            f"local environment has not been initialized; missing config files: {names}"
        ),
        command="apeiria env init",
    )


def _config_filename(key: str) -> str:
    return {
        "main_config": "apeiria.config.toml",
        "plugin_config": "apeiria.plugins.toml",
        "adapter_config": "apeiria.adapters.toml",
        "driver_config": "apeiria.drivers.toml",
    }[key]


def _deduplicate_issues(
    issues: list[EntryEnvironmentIssue],
) -> tuple[EntryEnvironmentIssue, ...]:
    seen: set[tuple[str, str]] = set()
    result: list[EntryEnvironmentIssue] = []
    for issue in issues:
        identity = (issue.key, issue.command)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(issue)
    return tuple(result)
