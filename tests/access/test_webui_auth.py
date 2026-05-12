from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

EXPECTED_UPDATED_SESSION_VERSION = 1
EXPECTED_ROTATED_SESSION_VERSION = 2


def _clear_webui_auth_modules() -> None:
    for module_name in (
        "apeiria.access.webui_auth",
        "apeiria.access.webui_auth.accounts",
        "apeiria.access.webui_auth.audit",
        "apeiria.access.webui_auth.secrets",
        "apeiria.access.webui_auth.service",
        "apeiria.access.webui_auth.store",
        "apeiria.app.access.webui_auth",
        "apeiria.app.access.webui_auth.accounts",
        "apeiria.app.access.webui_auth.audit",
        "apeiria.app.access.webui_auth.secrets",
        "apeiria.app.access.webui_auth.service",
        "apeiria.app.access.webui_auth.store",
    ):
        sys.modules.pop(module_name, None)


def test_webui_auth_account_flow_still_works_via_app_secrets_facade(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_webui_auth_modules()

    secret_file = tmp_path / "data" / "web_ui" / "secret.json"
    stub_localstore = ModuleType("nonebot_plugin_localstore")
    stub_localstore.get_data_file = _stub_get_data_file(secret_file)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nonebot_plugin_localstore", stub_localstore)

    secrets_module = importlib.import_module("apeiria.app.access.webui_auth.secrets")
    audit_module = importlib.import_module("apeiria.app.access.webui_auth.audit")
    monkeypatch.setattr(audit_module, "_mirror_to_governance_audit", _noop_mirror)

    created_code = secrets_module.create_registration_code(
        role="owner",
        created_by="host",
    )
    registered = secrets_module.register_account(
        created_code.code,
        "Alice",
        "strong-pass-123",
    )
    verified = secrets_module.verify_account_password("alice", "strong-pass-123")
    updated = secrets_module.update_account_password(
        registered.user_id,
        "fresh-pass-456",
    )
    rotated = secrets_module.rotate_account_session_version(
        registered.user_id,
        actor_username="alice",
    )

    assert secrets_module.get_secret_file_path() == secret_file
    assert verified is not None
    assert verified.username == "alice"
    assert updated is not None
    assert updated.session_version == EXPECTED_UPDATED_SESSION_VERSION
    assert secrets_module.verify_account_password("alice", "strong-pass-123") is None
    assert secrets_module.verify_account_password("alice", "fresh-pass-456") is not None
    assert rotated is not None
    assert rotated.session_version == EXPECTED_ROTATED_SESSION_VERSION
    assert [
        item.event_type for item in secrets_module.list_security_audit_events()
    ] == [
        "sessions_revoked",
        "password_changed",
        "registration_code_used",
        "registration_code_created",
    ]
    assert secret_file.is_file()


def _noop_mirror(*_args: object, **_kwargs: object) -> None:
    return None


def _stub_get_data_file(secret_file: Path):
    def get_data_file(_plugin: str, _name: str) -> Path:
        return secret_file

    return get_data_file
