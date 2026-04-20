"""Future-task boundary exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import (
        AIFutureTaskCreateInput,
        AIFutureTaskDefinition,
        AIFutureTaskStatus,
        AIFutureTaskToolAction,
        AIFutureTaskToolInput,
        AIFutureTaskToolItem,
        AIFutureTaskToolOutput,
    )
    from .service import (
        AIFutureTaskCreateResult,
        AIFutureTaskService,
        ai_future_task_service,
        execute_future_task,
    )

__all__ = [
    "AIFutureTaskCreateInput",
    "AIFutureTaskCreateResult",
    "AIFutureTaskDefinition",
    "AIFutureTaskService",
    "AIFutureTaskStatus",
    "AIFutureTaskToolAction",
    "AIFutureTaskToolInput",
    "AIFutureTaskToolItem",
    "AIFutureTaskToolOutput",
    "ai_future_task_service",
    "execute_future_task",
]

_LAZY_EXPORTS = {
    "AIFutureTaskCreateInput": ".models",
    "AIFutureTaskDefinition": ".models",
    "AIFutureTaskStatus": ".models",
    "AIFutureTaskToolAction": ".models",
    "AIFutureTaskToolInput": ".models",
    "AIFutureTaskToolItem": ".models",
    "AIFutureTaskToolOutput": ".models",
    "AIFutureTaskCreateResult": ".service",
    "AIFutureTaskService": ".service",
    "ai_future_task_service": ".service",
    "execute_future_task": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
