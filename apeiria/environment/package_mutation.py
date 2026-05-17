from __future__ import annotations

import contextlib
import fcntl
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.environment.package_progress import current_package_progress_reporter
from apeiria.utils.project_context import current_project_root

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_PROCESS_LOCK = threading.RLock()
_LOCAL = threading.local()


@dataclass(frozen=True)
class PackageMutationLockInfo:
    """Observed project-local package mutation lock paths."""

    project_root: Path
    lock_path: Path


def package_mutation_lock_info() -> PackageMutationLockInfo:
    project_root = current_project_root()
    return PackageMutationLockInfo(
        project_root=project_root,
        lock_path=project_root / ".apeiria" / "locks" / "package-mutations.lock",
    )


@contextlib.contextmanager
def package_mutation_lock() -> "Iterator[PackageMutationLockInfo]":
    """Serialize package mutations across process threads and CLI processes."""

    with _PROCESS_LOCK:
        depth = int(getattr(_LOCAL, "depth", 0))
        _LOCAL.depth = depth + 1
        lock_info = package_mutation_lock_info()
        lock_file = None
        try:
            if depth == 0:
                lock_info.lock_path.parent.mkdir(parents=True, exist_ok=True)
                reporter = current_package_progress_reporter()
                reporter.waiting_for_lock(str(lock_info.lock_path))
                lock_file = lock_info.lock_path.open("a+", encoding="utf-8")
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                reporter.lock_acquired(str(lock_info.lock_path))
            yield lock_info
        finally:
            if lock_file is not None:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                finally:
                    lock_file.close()
            next_depth = int(getattr(_LOCAL, "depth", 1)) - 1
            if next_depth <= 0:
                with contextlib.suppress(AttributeError):
                    delattr(_LOCAL, "depth")
            else:
                _LOCAL.depth = next_depth


__all__ = [
    "PackageMutationLockInfo",
    "package_mutation_lock",
    "package_mutation_lock_info",
]
