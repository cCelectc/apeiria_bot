from __future__ import annotations

import importlib
import json
import sys
from typing import TYPE_CHECKING

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.utils.project_context import (
    reset_active_project_root,
    set_active_project_root,
)

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


def test_webui_auth_account_flow_uses_current_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_webui_auth_modules()

    token = set_active_project_root(tmp_path)
    secret_file = tmp_path / "data" / "web_ui" / "secret.json"
    secret_file.parent.mkdir(parents=True)
    secret_file.write_text(
        json.dumps(
            {
                "token_secret": "legacy-token-secret",
                "users": [],
                "registration_codes": [],
                "audit_events": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        secrets_module = importlib.import_module(
            "apeiria.app.access.webui_auth.secrets"
        )
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
        assert secrets_module.get_token_secret() == "legacy-token-secret"
        assert verified is not None
        assert verified.username == "alice"
        assert updated is not None
        assert updated.session_version == EXPECTED_UPDATED_SESSION_VERSION
        assert (
            secrets_module.verify_account_password("alice", "strong-pass-123") is None
        )
        assert (
            secrets_module.verify_account_password("alice", "fresh-pass-456")
            is not None
        )
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
        assert not secret_file.is_file()
        assert secret_file.with_name("secret.json.v1.backup").is_file()
        assert ApeiriaDatabase(project_root=tmp_path).database_path().is_file()
    finally:
        reset_active_project_root(token)


def _noop_mirror(*_args: object, **_kwargs: object) -> None:
    return None
