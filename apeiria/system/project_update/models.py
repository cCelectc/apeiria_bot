"""Project update data models, type aliases, and exceptions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

ProjectUpdateChannel = Literal["branch", "release"]
ProjectUpdateOperation = Literal["update", "rollback"]
ProjectUpdateReleaseTrack = Literal["stable", "prerelease"]
ProjectUpdateTaskStatus = Literal["queued", "running", "succeeded", "failed"]

_SEMVER_TAG_RE = re.compile(
    r"^v?"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?"
    r"$"
)
_SECRET_VALUE_RE = re.compile(r"(?i)\b(token|password|secret|api[_-]?key)=([^\s&]+)")
_URL_CREDENTIAL_RE = re.compile(r"([a-z][a-z0-9+.-]*://)([^/@\s]+)@")
_OUTPUT_EXCERPT_LIMIT = 4000
_DEPLOY_BRANCH = "apeiria-release-deploy"
_AHEAD_BEHIND_PART_COUNT = 2
_REMOTE_REFRESH_TTL_SECONDS = 30 * 60
_REMOTE_REFRESH_ERROR_BACKOFF_SECONDS = 5 * 60


@dataclass(frozen=True, slots=True)
class ProjectUpdateMessage:
    code: str
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class SemverTag:
    raw: str
    normalized: str
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: str | None = None

    @property
    def is_prerelease(self) -> bool:
        return bool(self.prerelease)

    @property
    def public_version(self) -> str:
        return self.normalized


@dataclass(frozen=True, slots=True)
class ProjectReleaseMetadata:
    version: str | None = None
    database_schema_min: int | None = None
    database_schema_max: int | None = None
    requires_python: str | None = None
    source: str | None = None
    available: bool = False


@dataclass(frozen=True, slots=True)
class ProjectReleaseCandidate:
    tag: str
    version: str
    commit: str
    prerelease: bool
    metadata: ProjectReleaseMetadata
    is_current: bool = False
    is_rollback: bool = False
    blockers: tuple[ProjectUpdateMessage, ...] = ()
    warnings: tuple[ProjectUpdateMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class GitCheckoutState:
    project_root: Path
    is_git: bool
    is_detached: bool = False
    branch: str | None = None
    current_commit: str | None = None
    short_commit: str | None = None
    upstream_ref: str | None = None
    upstream_commit: str | None = None
    ahead: int | None = None
    behind: int | None = None
    dirty: bool = False
    dirty_entries: tuple[str, ...] = ()
    head_tags: tuple[str, ...] = ()
    blockers: tuple[ProjectUpdateMessage, ...] = ()

    @property
    def diverged(self) -> bool:
        return bool(self.ahead and self.behind)


@dataclass(frozen=True, slots=True)
class BranchUpdateState:
    available: bool
    target_ref: str | None = None
    target_commit: str | None = None
    blockers: tuple[ProjectUpdateMessage, ...] = ()
    warnings: tuple[ProjectUpdateMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectUpdateRemoteRefreshState:
    ttl_seconds: int
    stale: bool
    last_checked_at: str | None = None
    last_success_at: str | None = None
    next_check_after: str | None = None
    last_error_at: str | None = None
    last_error: str | None = None
    remotes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectUpdateStatus:
    project_root: Path
    checkout: GitCheckoutState
    branch: BranchUpdateState
    remote_refresh: ProjectUpdateRemoteRefreshState
    stable_releases: tuple[ProjectReleaseCandidate, ...] = ()
    prerelease_releases: tuple[ProjectReleaseCandidate, ...] = ()
    active_task: "ProjectUpdateTask | None" = None


@dataclass(frozen=True, slots=True)
class ProjectUpdatePlanRequest:
    channel: ProjectUpdateChannel
    release_track: ProjectUpdateReleaseTrack | None = None
    target_tag: str | None = None
    operation: ProjectUpdateOperation | None = None


@dataclass(frozen=True, slots=True)
class ProjectUpdatePlan:
    channel: ProjectUpdateChannel
    operation: ProjectUpdateOperation
    target_ref: str | None
    target_commit: str | None
    release_track: ProjectUpdateReleaseTrack | None = None
    target_tag: str | None = None
    target_version: str | None = None
    blockers: tuple[ProjectUpdateMessage, ...] = ()
    warnings: tuple[ProjectUpdateMessage, ...] = ()
    steps: tuple[str, ...] = ()
    confirmation: str = "update"

    @property
    def allowed(self) -> bool:
        return not self.blockers and bool(self.target_ref and self.target_commit)


@dataclass(frozen=True, slots=True)
class ProjectUpdateTaskStep:
    phase: str
    label: str
    status: str
    detail: str | None = None
    command: str | None = None
    output_excerpt: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectUpdateTask:
    task_id: str
    title: str
    status: ProjectUpdateTaskStatus
    logs: str
    error: str | None = None
    result: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    channel: ProjectUpdateChannel | None = None
    operation: ProjectUpdateOperation | None = None
    target_ref: str | None = None
    target_commit: str | None = None
    target_tag: str | None = None
    target_version: str | None = None
    current_phase: str | None = None
    current_phase_label: str | None = None
    progress_percent: int | None = None
    restart_required: bool = False
    steps: tuple[ProjectUpdateTaskStep, ...] = ()
    diagnostics: tuple[dict[str, object], ...] = ()


class ProjectUpdateError(RuntimeError):
    """Raised when one project update operation cannot proceed."""


class GitCommandError(ProjectUpdateError):
    """Raised when a git command fails."""


def _message(
    code: str,
    message: str,
    detail: str | None = None,
) -> ProjectUpdateMessage:
    return ProjectUpdateMessage(code=code, message=message, detail=detail)
