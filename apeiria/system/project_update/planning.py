"""Project update planning helpers."""

from __future__ import annotations

import sys

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from apeiria.system.project_update.models import (
    GitCheckoutState,
    ProjectReleaseCandidate,
    ProjectUpdateChannel,
    ProjectUpdateMessage,
    ProjectUpdateOperation,
    ProjectUpdatePlan,
    ProjectUpdateReleaseTrack,
    _message,
)


def _checkout_blockers(
    checkout: GitCheckoutState,
) -> tuple[ProjectUpdateMessage, ...]:
    blockers: list[ProjectUpdateMessage] = []
    if not checkout.is_git:
        blockers.append(
            _message("not_git_checkout", "Project root is not a git checkout.")
        )
    if checkout.is_detached:
        blockers.append(
            _message("detached_head", "Project checkout is in detached HEAD state.")
        )
    if checkout.dirty:
        blockers.append(
            _message("dirty_worktree", "Project worktree has local changes.")
        )
    return tuple(blockers)


def _select_release_candidate(
    candidates: tuple[ProjectReleaseCandidate, ...],
    target_tag: str | None,
) -> ProjectReleaseCandidate | None:
    if target_tag is None:
        return candidates[0] if candidates else None
    for candidate in candidates:
        if candidate.tag == target_tag:
            return candidate
    return None


def _python_requirement_blocker(requirement: str) -> ProjectUpdateMessage | None:
    try:
        specifier = SpecifierSet(requirement)
    except InvalidSpecifier:
        return _message(
            "python_requirement_invalid",
            "Target release has an invalid Python requirement.",
            requirement,
        )
    version = Version(
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    if version not in specifier:
        return _message(
            "python_requirement_unsupported",
            "Current Python version does not satisfy the target release.",
            requirement,
        )
    return None


def _blocked_plan(  # noqa: PLR0913
    *,
    channel: ProjectUpdateChannel,
    operation: ProjectUpdateOperation,
    blocker: ProjectUpdateMessage,
    release_track: ProjectUpdateReleaseTrack | None = None,
    target_tag: str | None = None,
    target_commit: str | None = None,
) -> ProjectUpdatePlan:
    return ProjectUpdatePlan(
        channel=channel,
        operation=operation,
        target_ref=f"refs/tags/{target_tag}" if target_tag else None,
        target_commit=target_commit,
        release_track=release_track,
        target_tag=target_tag,
        blockers=(blocker,),
        confirmation="rollback" if operation == "rollback" else "update",
    )


def _task_title(plan: ProjectUpdatePlan) -> str:
    if plan.channel == "branch":
        return f"Update branch from {plan.target_ref}"
    if plan.operation == "rollback":
        return f"Rollback to {plan.target_tag}"
    return f"Update to {plan.target_tag}"
