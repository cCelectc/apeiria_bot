"""Progress reporting hooks for package mutations."""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator


class PackageProgressReporter(Protocol):
    """Receive package mutation progress events."""

    def waiting_for_lock(self, lock_path: str) -> None: ...

    def lock_acquired(self, lock_path: str) -> None: ...

    def step_started(
        self,
        phase: str,
        label: str,
        *,
        detail: str | None = None,
        command: str | None = None,
    ) -> None: ...

    def step_finished(
        self,
        phase: str,
        *,
        status: str = "succeeded",
        detail: str | None = None,
        output_excerpt: str | None = None,
    ) -> None: ...

    def diagnostic(self, phase: str, message: str) -> None: ...


class _NoopPackageProgressReporter:
    def waiting_for_lock(self, lock_path: str) -> None:
        del lock_path

    def lock_acquired(self, lock_path: str) -> None:
        del lock_path

    def step_started(
        self,
        phase: str,
        label: str,
        *,
        detail: str | None = None,
        command: str | None = None,
    ) -> None:
        del phase, label, detail, command

    def step_finished(
        self,
        phase: str,
        *,
        status: str = "succeeded",
        detail: str | None = None,
        output_excerpt: str | None = None,
    ) -> None:
        del phase, status, detail, output_excerpt

    def diagnostic(self, phase: str, message: str) -> None:
        del phase, message


_NOOP_REPORTER = _NoopPackageProgressReporter()
_CURRENT_REPORTER: contextvars.ContextVar[PackageProgressReporter | None] = (
    contextvars.ContextVar("apeiria_package_progress_reporter", default=None)
)


def current_package_progress_reporter() -> PackageProgressReporter:
    """Return the active package progress reporter or a no-op reporter."""

    return _CURRENT_REPORTER.get() or _NOOP_REPORTER


@contextlib.contextmanager
def use_package_progress_reporter(
    reporter: PackageProgressReporter | None,
) -> "Iterator[None]":
    """Temporarily bind a package progress reporter to the current context."""

    if reporter is None:
        yield
        return

    token = _CURRENT_REPORTER.set(reporter)
    try:
        yield
    finally:
        _CURRENT_REPORTER.reset(token)


__all__ = [
    "PackageProgressReporter",
    "current_package_progress_reporter",
    "use_package_progress_reporter",
]
