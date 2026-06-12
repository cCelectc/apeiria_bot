from __future__ import annotations

import importlib
import json
import sys
from typing import TYPE_CHECKING

import pytest

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.utils.project_context import (
    reset_active_project_root,
    set_active_project_root,
)
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


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


@pytest.mark.anyio
async def test_webui_auth_account_flow_uses_current_storage(
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
            }
        ),
        encoding="utf-8",
    )

    database = ApeiriaDatabase(project_root=tmp_path)
    database.ensure_ready()

    try:
        async with async_db(database.database_path(), create_tables=False):
            secrets_module = importlib.import_module(
                "apeiria.app.access.webui_auth.secrets"
            )
            created_username, created = await secrets_module.recover_owner_account(
                "Alice",
                "strong-pass-123",
            )
            assert created_username == "alice"
            assert created is True
            registered = await secrets_module.get_account_by_username("alice")
            assert registered is not None
            verified = await secrets_module.verify_account_password(
                "alice", "strong-pass-123"
            )
            updated = await secrets_module.update_account_password(
                registered.user_id,
                "fresh-pass-456",
            )
            rotated = await secrets_module.rotate_account_session_version(
                registered.user_id,
            )

            assert secrets_module.get_secret_file_path() == secret_file
            assert await secrets_module.get_token_secret() == "legacy-token-secret"
            assert verified is not None
            assert verified.username == "alice"
            assert updated is not None
            assert updated.session_version == EXPECTED_UPDATED_SESSION_VERSION
            assert (
                await secrets_module.verify_account_password(
                    "alice", "strong-pass-123"
                )
                is None
            )
            assert (
                await secrets_module.verify_account_password(
                    "alice", "fresh-pass-456"
                )
                is not None
            )
            assert rotated is not None
            assert rotated.session_version == EXPECTED_ROTATED_SESSION_VERSION
            assert not secret_file.is_file()
            assert secret_file.with_name("secret.json.v1.backup").is_file()
            assert ApeiriaDatabase(project_root=tmp_path).database_path().is_file()
    finally:
        reset_active_project_root(token)
