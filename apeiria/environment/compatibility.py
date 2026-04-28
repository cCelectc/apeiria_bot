"""Non-mutating diagnostics for retired local project compatibility state."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apeiria.utils.files import load_toml_dict

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("apeiria.environment.compatibility")

_WEB_UI_TOKEN_KEY = "web_ui_token_expire_days"


@dataclass(frozen=True, slots=True)
class RetiredProjectStateIssue:
    """One stale local state shape that needs explicit operator migration."""

    key: str
    message: str
    hint: str


def inspect_retired_project_state(
    project_root: "Path",
) -> tuple[RetiredProjectStateIssue, ...]:
    """Inspect retired project-local state without mutating files."""

    issues: list[RetiredProjectStateIssue] = []
    issues.extend(_inspect_web_ui_config(project_root / "apeiria.config.toml"))
    issues.extend(
        _inspect_web_ui_auth(project_root / "data" / "web_ui" / "secret.json")
    )
    return tuple(issues)


def _inspect_web_ui_config(
    config_path: "Path",
) -> tuple[RetiredProjectStateIssue, ...]:
    if not config_path.is_file():
        return ()
    data = load_toml_dict(
        config_path,
        logger=logger,
        missing_dependency_message=(
            f"Skip loading {config_path.name}: tomllib/tomli is unavailable"
        ),
    )
    nonebot = data.get("nonebot")
    has_retired_key = _WEB_UI_TOKEN_KEY in data or (
        isinstance(nonebot, dict) and _WEB_UI_TOKEN_KEY in nonebot
    )
    if not has_retired_key:
        return ()
    return (
        RetiredProjectStateIssue(
            key="web_ui_token_expire_days",
            message="Retired Web UI global config key is present.",
            hint=(
                "Move `web_ui_token_expire_days` to "
                "`[plugins.web_ui].token_expire_days`, then remove the global key."
            ),
        ),
    )


def _inspect_web_ui_auth(
    secret_file: "Path",
) -> tuple[RetiredProjectStateIssue, ...]:
    if not secret_file.is_file():
        return ()
    try:
        data = json.loads(secret_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(data, dict):
        return ()
    if not _is_legacy_auth_shape(data):
        return ()
    return (
        RetiredProjectStateIssue(
            key="web_ui_auth_legacy_schema",
            message="Legacy Web UI auth storage schema is present.",
            hint=(
                "Migrate or recreate `data/web_ui/secret.json` with the current "
                "account schema before startup."
            ),
        ),
    )


def _is_legacy_auth_shape(data: dict[str, Any]) -> bool:
    if "password" in data or "invite_codes" in data:
        return True
    registration_codes = data.get("registration_codes")
    return isinstance(registration_codes, list) and any(
        isinstance(item, str) for item in registration_codes
    )


__all__ = [
    "RetiredProjectStateIssue",
    "inspect_retired_project_state",
]
