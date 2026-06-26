from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nonebot.log import logger

StepFn = Callable[..., Any]


class BootstrapPlan:
    def __init__(self) -> None:
        self._steps: dict[str, StepFn] = {}
        self._depends: dict[str, list[str]] = {}

    def add_step(self, name: str, fn: StepFn, depends: list[str] | None = None) -> None:
        self._steps[name] = fn
        self._depends[name] = list(depends or [])

    def run(self, plan_name: str) -> BootstrapResult:
        logger.info("Running bootstrap plan: {}", plan_name)
        order = _topo_sort(self._steps, self._depends)

        success: list[str] = []
        failed: list[str] = []

        for name in order:
            fn = self._steps[name]
            logger.debug("Bootstrap step: {}", name)
            try:
                fn()
                success.append(name)
            except Exception:  # noqa: BLE001
                logger.opt(exception=True).error("Bootstrap step failed: {}", name)
                failed.append(name)

        logger.success(
            "Bootstrap complete: {} succeeded, {} failed",
            len(success),
            len(failed),
        )
        return BootstrapResult(success=tuple(success), failed=tuple(failed))


class BootstrapResult:
    __slots__ = ("failed", "success")

    def __init__(self, success: tuple[str, ...], failed: tuple[str, ...]) -> None:
        self.success = success
        self.failed = failed

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0


def _topo_sort(
    steps: dict[str, StepFn],
    depends: dict[str, list[str]],
) -> list[str]:
    in_degree: dict[str, int] = dict.fromkeys(steps, 0)

    for name, deps in depends.items():
        for _dep in deps:
            in_degree[name] += 1

    queue = [name for name, deg in in_degree.items() if deg == 0]
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for other_name, other_deps in depends.items():
            if node in other_deps:
                in_degree[other_name] -= 1
                if in_degree[other_name] == 0:
                    queue.append(other_name)

    if len(result) != len(steps):
        missing = set(steps) - set(result)
        logger.warning("Bootstrap cycle or missing deps: {}", missing)

    return result
