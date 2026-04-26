"""Persistent Web UI authentication storage."""

from __future__ import annotations

from apeiria.access.webui_auth.accounts import (
    WebUIAccount,
    WebUIRegistrationCode,
    create_account,
    create_registration_code,
    delete_account,
    get_account_by_id,
    get_account_by_username,
    list_accounts,
    list_registration_codes,
    record_login_success,
    recover_owner_account,
    register_account,
    revoke_registration_code,
    rotate_account_session_version,
    set_account_disabled,
    set_account_password,
    update_account_password,
    update_account_role,
    verify_account_password,
)
from apeiria.access.webui_auth.audit import (
    WebUISecurityAuditEvent,
    list_security_audit_events,
    record_security_audit_event,
)
from apeiria.access.webui_auth.store import (
    get_secret_file_path,
    get_token_secret,
)

__all__ = [
    "WebUIAccount",
    "WebUIRegistrationCode",
    "WebUISecurityAuditEvent",
    "create_account",
    "create_registration_code",
    "delete_account",
    "get_account_by_id",
    "get_account_by_username",
    "get_secret_file_path",
    "get_token_secret",
    "list_accounts",
    "list_registration_codes",
    "list_security_audit_events",
    "record_login_success",
    "record_security_audit_event",
    "recover_owner_account",
    "register_account",
    "revoke_registration_code",
    "rotate_account_session_version",
    "set_account_disabled",
    "set_account_password",
    "update_account_password",
    "update_account_role",
    "verify_account_password",
]
