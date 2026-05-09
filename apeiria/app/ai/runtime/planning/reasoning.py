"""Small deterministic runtime reasoning policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.runtime.capabilities import (
    AI_MODEL_REASONING_EFFORT_OPTION,
    AIModelCallOptions,
)

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelTaskClass


def reasoning_options_for_task_class(
    task_class: "AIModelTaskClass | None",
) -> AIModelCallOptions | None:
    """Return optional reasoning options for explicit heavy tasks only."""

    if task_class != "reasoning_heavy":
        return None
    return AIModelCallOptions(values={AI_MODEL_REASONING_EFFORT_OPTION: "medium"})


__all__ = ["reasoning_options_for_task_class"]
