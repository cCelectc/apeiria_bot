"""Persistent Web UI authentication storage."""

from __future__ import annotations

from apeiria.webui.auth.accounts import (
    WebUIAccount,
    create_account,
    delete_account,
    get_account_by_id,
    get_account_by_username,
    list_accounts,
    record_login_success,
    recover_owner_account,
    reset_account_password,
    set_account_password,
    update_account_password,
    verify_account_password,
)
from apeiria.webui.auth.audit import (
    WebUISecurityAuditEvent,
    list_security_audit_events,
    record_security_audit_event,
)
from apeiria.webui.auth.store import (
    get_secret_file_path,
)

__all__ = [
    "WebUIAccount",
    "WebUISecurityAuditEvent",
    "create_account",
    "delete_account",
    "get_account_by_id",
    "get_account_by_username",
    "get_secret_file_path",
    "list_accounts",
    "list_security_audit_events",
    "record_login_success",
    "record_security_audit_event",
    "recover_owner_account",
    "reset_account_password",
    "set_account_password",
    "update_account_password",
    "verify_account_password",
]
