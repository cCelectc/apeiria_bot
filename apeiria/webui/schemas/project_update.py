"""Project update Web UI schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ProjectUpdateMessageItem(BaseModel):
    code: str
    message: str
    detail: str | None = None


class ProjectReleaseMetadataItem(BaseModel):
    version: str | None = None
    database_schema_min: int | None = None
    database_schema_max: int | None = None
    requires_python: str | None = None
    source: str | None = None
    available: bool = False


class ProjectReleaseCandidateItem(BaseModel):
    tag: str
    version: str
    commit: str
    prerelease: bool
    metadata: ProjectReleaseMetadataItem
    is_current: bool = False
    is_rollback: bool = False
    blockers: list[ProjectUpdateMessageItem] = []
    warnings: list[ProjectUpdateMessageItem] = []


class GitCheckoutStateItem(BaseModel):
    project_root: str
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
    dirty_entries: list[str] = []
    head_tags: list[str] = []
    blockers: list[ProjectUpdateMessageItem] = []


class BranchUpdateStateItem(BaseModel):
    available: bool
    target_ref: str | None = None
    target_commit: str | None = None
    blockers: list[ProjectUpdateMessageItem] = []
    warnings: list[ProjectUpdateMessageItem] = []


class ProjectUpdateRemoteRefreshStateItem(BaseModel):
    ttl_seconds: int
    stale: bool
    last_checked_at: str | None = None
    last_success_at: str | None = None
    next_check_after: str | None = None
    last_error_at: str | None = None
    last_error: str | None = None
    remotes: list[str] = []


class ProjectUpdateTaskStepItem(BaseModel):
    phase: str
    label: str
    status: str
    detail: str | None = None
    command: str | None = None
    output_excerpt: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class ProjectUpdateTaskItem(BaseModel):
    task_id: str
    title: str
    status: str
    logs: str
    error: str | None = None
    result: dict[str, object] = {}
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    channel: str | None = None
    operation: str | None = None
    target_ref: str | None = None
    target_commit: str | None = None
    target_tag: str | None = None
    target_version: str | None = None
    current_phase: str | None = None
    current_phase_label: str | None = None
    progress_percent: int | None = None
    restart_required: bool = False
    steps: list[ProjectUpdateTaskStepItem] = []
    diagnostics: list[dict[str, object]] = []


class ProjectUpdateStatusResponse(BaseModel):
    project_root: str
    checkout: GitCheckoutStateItem
    branch: BranchUpdateStateItem
    remote_refresh: ProjectUpdateRemoteRefreshStateItem
    stable_releases: list[ProjectReleaseCandidateItem] = []
    prerelease_releases: list[ProjectReleaseCandidateItem] = []
    active_task: ProjectUpdateTaskItem | None = None


class ProjectUpdatePlanRequest(BaseModel):
    channel: Literal["branch", "release"]
    release_track: Literal["stable", "prerelease"] | None = None
    target_tag: str | None = Field(default=None, max_length=128)
    operation: Literal["update", "rollback"] | None = None

    @model_validator(mode="after")
    def validate_release_fields(self) -> "ProjectUpdatePlanRequest":
        if self.channel == "branch":
            if self.release_track is not None or self.target_tag is not None:
                msg = "branch updates do not accept release fields"
                raise ValueError(msg)
            return self
        if self.release_track is None:
            self.release_track = "stable"
        return self


class ProjectUpdatePlanResponse(BaseModel):
    channel: str
    operation: str
    target_ref: str | None = None
    target_commit: str | None = None
    release_track: str | None = None
    target_tag: str | None = None
    target_version: str | None = None
    allowed: bool
    blockers: list[ProjectUpdateMessageItem] = []
    warnings: list[ProjectUpdateMessageItem] = []
    steps: list[str] = []
    confirmation: str


def to_project_update_status_response(state: Any) -> ProjectUpdateStatusResponse:
    return ProjectUpdateStatusResponse(
        project_root=str(state.project_root),
        checkout=_checkout_item(state.checkout),
        branch=_branch_item(state.branch),
        remote_refresh=_remote_refresh_item(state.remote_refresh),
        stable_releases=[_release_item(item) for item in state.stable_releases],
        prerelease_releases=[_release_item(item) for item in state.prerelease_releases],
        active_task=(
            to_project_update_task_item(state.active_task)
            if state.active_task is not None
            else None
        ),
    )


def to_project_update_plan_request(payload: ProjectUpdatePlanRequest) -> Any:
    from apeiria.app.system.project_update import ProjectUpdatePlanRequest as Domain

    return Domain(
        channel=payload.channel,
        release_track=payload.release_track,
        target_tag=payload.target_tag,
        operation=payload.operation,
    )


def to_project_update_plan_response(plan: Any) -> ProjectUpdatePlanResponse:
    return ProjectUpdatePlanResponse(
        channel=plan.channel,
        operation=plan.operation,
        target_ref=plan.target_ref,
        target_commit=plan.target_commit,
        release_track=plan.release_track,
        target_tag=plan.target_tag,
        target_version=plan.target_version,
        allowed=plan.allowed,
        blockers=[_message_item(item) for item in plan.blockers],
        warnings=[_message_item(item) for item in plan.warnings],
        steps=list(plan.steps),
        confirmation=plan.confirmation,
    )


def to_project_update_task_item(task: Any) -> ProjectUpdateTaskItem:
    return ProjectUpdateTaskItem(
        task_id=task.task_id,
        title=task.title,
        status=task.status,
        logs=task.logs,
        error=task.error,
        result=task.result,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        channel=task.channel,
        operation=task.operation,
        target_ref=task.target_ref,
        target_commit=task.target_commit,
        target_tag=task.target_tag,
        target_version=task.target_version,
        current_phase=task.current_phase,
        current_phase_label=task.current_phase_label,
        progress_percent=task.progress_percent,
        restart_required=task.restart_required,
        steps=[
            ProjectUpdateTaskStepItem(
                phase=step.phase,
                label=step.label,
                status=step.status,
                detail=step.detail,
                command=step.command,
                output_excerpt=step.output_excerpt,
                started_at=step.started_at,
                finished_at=step.finished_at,
            )
            for step in task.steps
        ],
        diagnostics=list(task.diagnostics),
    )


def _checkout_item(item: Any) -> GitCheckoutStateItem:
    return GitCheckoutStateItem(
        project_root=str(item.project_root),
        is_git=item.is_git,
        is_detached=item.is_detached,
        branch=item.branch,
        current_commit=item.current_commit,
        short_commit=item.short_commit,
        upstream_ref=item.upstream_ref,
        upstream_commit=item.upstream_commit,
        ahead=item.ahead,
        behind=item.behind,
        dirty=item.dirty,
        dirty_entries=list(item.dirty_entries),
        head_tags=list(item.head_tags),
        blockers=[_message_item(message) for message in item.blockers],
    )


def _branch_item(item: Any) -> BranchUpdateStateItem:
    return BranchUpdateStateItem(
        available=item.available,
        target_ref=item.target_ref,
        target_commit=item.target_commit,
        blockers=[_message_item(message) for message in item.blockers],
        warnings=[_message_item(message) for message in item.warnings],
    )


def _remote_refresh_item(item: Any) -> ProjectUpdateRemoteRefreshStateItem:
    return ProjectUpdateRemoteRefreshStateItem(
        ttl_seconds=item.ttl_seconds,
        stale=item.stale,
        last_checked_at=item.last_checked_at,
        last_success_at=item.last_success_at,
        next_check_after=item.next_check_after,
        last_error_at=item.last_error_at,
        last_error=item.last_error,
        remotes=list(item.remotes),
    )


def _release_item(item: Any) -> ProjectReleaseCandidateItem:
    return ProjectReleaseCandidateItem(
        tag=item.tag,
        version=item.version,
        commit=item.commit,
        prerelease=item.prerelease,
        metadata=ProjectReleaseMetadataItem(
            version=item.metadata.version,
            database_schema_min=item.metadata.database_schema_min,
            database_schema_max=item.metadata.database_schema_max,
            requires_python=item.metadata.requires_python,
            source=item.metadata.source,
            available=item.metadata.available,
        ),
        is_current=item.is_current,
        is_rollback=item.is_rollback,
        blockers=[_message_item(message) for message in item.blockers],
        warnings=[_message_item(message) for message in item.warnings],
    )


def _message_item(item: Any) -> ProjectUpdateMessageItem:
    return ProjectUpdateMessageItem(
        code=item.code,
        message=item.message,
        detail=item.detail,
    )
