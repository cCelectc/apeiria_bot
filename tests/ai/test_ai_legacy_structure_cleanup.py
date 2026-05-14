from __future__ import annotations

import importlib.util


def test_active_runtime_contracts_are_direct_imports() -> None:
    from apeiria.app.ai.runtime.contracts import (
        FutureTaskRuntimeResult,
        RuntimeTraceContext,
    )

    trace = RuntimeTraceContext(kind="conversation", trigger="ai_future_task")
    result = FutureTaskRuntimeResult(
        reply_text="ok",
        commit_status="committed",
        delivery_status="delivered",
    )

    assert trace.trigger == "ai_future_task"
    assert result.reply_text == "ok"


def test_legacy_runtime_entry_module_is_removed() -> None:
    assert importlib.util.find_spec("apeiria.app.ai.runtime.entry") is None


def test_runtime_package_does_not_export_deleted_runtime_names() -> None:
    from apeiria.app.ai import runtime

    deleted_names = {
        "AIRuntimeEntry",
        "AcceptedTurn",
        "RuntimeInput",
        "RuntimeTraceRecordInput",
        "TurnContextMaterials",
        "TurnExecutionResult",
        "TurnPlan",
        "TurnTrace",
        "RuntimeTraceContext",
        "CommitResult",
    }

    assert not deleted_names.intersection(dir(runtime))


def test_operations_entry_does_not_expose_removed_admin_methods() -> None:
    from apeiria.app.ai.operations import AIOperationsEntry

    entry = AIOperationsEntry()

    assert not hasattr(entry, "list_future_tasks")
    assert not hasattr(entry, "cancel_future_task")
    assert not hasattr(entry, "list_skills")
