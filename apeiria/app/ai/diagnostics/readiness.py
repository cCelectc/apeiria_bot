"""Read-only AI runtime readiness diagnostics."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from apeiria.ai.service import AIRuntimeDependencyStatus
from apeiria.db.inspection import inspect_database
from apeiria.db.runtime import database_runtime


class AIRuntimeReadinessProbe:
    """Inspect production AI runtime dependencies without mutating state."""

    def inspect(self) -> tuple[AIRuntimeDependencyStatus, ...]:
        return (
            self._future_task_storage_status(),
            self._delivery_attempt_storage_status(),
            self._scheduler_recovery_status(),
            *self._plugin_lifecycle_statuses(),
            self._delivery_gateway_status(),
            self._trace_storage_status(),
        )

    def _future_task_storage_status(self) -> AIRuntimeDependencyStatus:
        return _sqlite_table_status(
            key="future_task_storage",
            table_name="ai_future_task",
            required_columns={
                "task_id",
                "status",
                "trigger_at",
                "scheduler_job_id",
                "claim_count",
                "claimed_at",
                "completed_at",
                "recovery_reason",
            },
            unavailable_detail="unavailable",
            next_step="Run `apeiria check` to initialize runtime storage.",
        )

    def _delivery_attempt_storage_status(self) -> AIRuntimeDependencyStatus:
        return _sqlite_table_status(
            key="delivery_attempt_storage",
            table_name="ai_delivery_attempt",
            required_columns={
                "attempt_id",
                "task_id",
                "trace_id",
                "session_id",
                "delivery_intent",
                "status",
                "diagnostics_json",
                "remote_message_id",
                "attempt_count",
                "created_at",
                "updated_at",
            },
            unavailable_detail="unavailable",
            next_step="Run `apeiria check` to initialize delivery attempts.",
        )

    def _trace_storage_status(self) -> AIRuntimeDependencyStatus:
        return _sqlite_table_status(
            key="trace_storage",
            table_name="ai_turn_trace",
            required_columns={
                "trace_id",
                "session_id",
                "runtime_mode",
                "terminal_status",
                "delivery_status",
                "commit_status",
                "model_attempt_count",
                "tool_attempt_count",
                "skip_reason",
                "diagnostics_json",
                "created_at",
            },
            unavailable_detail="unavailable",
            next_step="Run `apeiria check` to repair trace storage.",
        )

    def _scheduler_recovery_status(self) -> AIRuntimeDependencyStatus:
        if _ai_plugin_registers_recovery_hook():
            return AIRuntimeDependencyStatus(
                key="scheduler_recovery",
                available=True,
                detail="registered",
            )
        return AIRuntimeDependencyStatus(
            key="scheduler_recovery",
            available=False,
            detail="not_registered",
            next_step="Load the AI plugin startup recovery hook.",
        )

    def _delivery_gateway_status(self) -> AIRuntimeDependencyStatus:
        from apeiria.app.ai.runtime.commit.delivery import delivery_gateway

        if delivery_gateway.can_deliver_platform("onebot"):
            return AIRuntimeDependencyStatus(
                key="delivery_gateway",
                available=True,
                detail="onebot",
            )
        return AIRuntimeDependencyStatus(
            key="delivery_gateway",
            available=False,
            detail="adapter_unavailable",
            next_step="Enable a proactive delivery adapter.",
        )

    def _plugin_lifecycle_statuses(self) -> tuple[AIRuntimeDependencyStatus, ...]:
        from apeiria.app.ai.lifecycle import ai_lifecycle_coordinator

        snapshot = ai_lifecycle_coordinator.inspect()
        return tuple(
            AIRuntimeDependencyStatus(
                key=component.key,
                available=component.available,
                detail=component.detail,
                next_step=component.next_step,
            )
            for component in snapshot.components
        )


def _sqlite_table_status(
    *,
    key: str,
    table_name: str,
    required_columns: set[str],
    unavailable_detail: str,
    next_step: str,
) -> AIRuntimeDependencyStatus:
    inspection = inspect_database(database_runtime.project_root)
    if not inspection.ready:
        return AIRuntimeDependencyStatus(
            key=key,
            available=False,
            detail=unavailable_detail,
            next_step=next_step,
        )
    if _sqlite_table_has_columns(
        database_path=inspection.path,
        table_name=table_name,
        required_columns=required_columns,
    ):
        return AIRuntimeDependencyStatus(
            key=key,
            available=True,
            detail="available",
        )
    return AIRuntimeDependencyStatus(
        key=key,
        available=False,
        detail=unavailable_detail,
        next_step=next_step,
    )


def _sqlite_table_has_columns(
    *,
    database_path: Path,
    table_name: str,
    required_columns: set[str],
) -> bool:
    try:
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    except sqlite3.DatabaseError:
        return False
    try:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.DatabaseError:
        return False
    finally:
        connection.close()
    columns = {str(row[1]) for row in rows}
    return required_columns <= columns


def _ai_plugin_registers_recovery_hook() -> bool:
    spec = importlib.util.find_spec("apeiria.builtin_plugins.ai")
    if spec is None or spec.origin is None:
        return False
    try:
        source = Path(spec.origin).read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        "ai_application.lifecycle.startup" in source
        and "on_startup(_run_ai_lifecycle_startup)" in source
    )


__all__ = ["AIRuntimeReadinessProbe"]
