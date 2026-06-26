"""Project update execution helpers (datetime, conversions, errors)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from apeiria.system.project_update.models import ProjectUpdateError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_datetime(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _blocked_update_plan_error(message: str) -> ProjectUpdateError:
    return ProjectUpdateError(message or "Project update plan is blocked.")


def _task_already_running_error() -> ProjectUpdateError:
    return ProjectUpdateError("project update task already running")


def _blocked_update_target_error(message: str) -> ProjectUpdateError:
    return ProjectUpdateError(message or "Project update target is blocked.")


def _target_changed_after_fetch_error() -> ProjectUpdateError:
    return ProjectUpdateError("Project update target changed after fetch.")


def _missing_branch_target_error() -> ProjectUpdateError:
    return ProjectUpdateError("Missing branch update target.")


def _missing_release_target_error() -> ProjectUpdateError:
    return ProjectUpdateError("Missing release update target.")


def _missing_branch_remote_error() -> ProjectUpdateError:
    return ProjectUpdateError("Missing branch upstream remote.")
