"""Project self-update workflows for owner-facing system operations."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import tomlkit

from apeiria.db.inspection import inspect_database
from apeiria.environment import environment_service
from apeiria.environment.package_mutation import package_mutation_lock
from apeiria.system.project_update.execution import (
    _blocked_update_plan_error,
    _blocked_update_target_error,
    _format_datetime,
    _int_or_none,
    _mapping_or_empty,
    _missing_branch_remote_error,
    _missing_branch_target_error,
    _missing_release_target_error,
    _now,
    _parse_datetime,
    _string_or_none,
    _target_changed_after_fetch_error,
    _task_already_running_error,
)
from apeiria.system.project_update.git import (
    _bounded_output,
    _command_error,
    _compare_semver,
    _semver_sort_key,
    parse_semver_tag,
    sanitize_output,
)
from apeiria.system.project_update.models import (
    _AHEAD_BEHIND_PART_COUNT,
    _DEPLOY_BRANCH,
    _REMOTE_REFRESH_ERROR_BACKOFF_SECONDS,
    _REMOTE_REFRESH_TTL_SECONDS,
    BranchUpdateState,
    GitCheckoutState,
    GitCommandError,
    ProjectReleaseCandidate,
    ProjectReleaseMetadata,
    ProjectUpdateMessage,
    ProjectUpdatePlan,
    ProjectUpdatePlanRequest,
    ProjectUpdateRemoteRefreshState,
    ProjectUpdateStatus,
    ProjectUpdateTask,
    ProjectUpdateTaskStep,
    SemverTag,
    _message,
)
from apeiria.system.project_update.planning import (
    _blocked_plan,
    _checkout_blockers,
    _python_requirement_blocker,
    _select_release_candidate,
    _task_title,
)
from apeiria.utils.project_context import current_project_root

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path


class ProjectUpdateService:
    """Inspect, plan, and execute guarded project self-updates."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = (
            project_root.resolve() if project_root is not None else None
        )
        self._tasks: dict[str, ProjectUpdateTask] = {}
        self._active_task_id: str | None = None
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._remote_refresh = ProjectUpdateRemoteRefreshState(
            ttl_seconds=_REMOTE_REFRESH_TTL_SECONDS,
            stale=True,
        )

    @property
    def project_root(self) -> Path:
        return self._project_root or current_project_root()

    def inspect(self) -> ProjectUpdateStatus:
        checkout = self.inspect_checkout()
        stable, prerelease = self.list_release_candidates(checkout)
        return ProjectUpdateStatus(
            project_root=self.project_root,
            checkout=checkout,
            branch=self._build_branch_state(checkout),
            remote_refresh=self._current_remote_refresh_state(),
            stable_releases=stable,
            prerelease_releases=prerelease,
            active_task=self.get_active_task(),
        )

    def refresh_remote_refs(self, *, force: bool = False) -> ProjectUpdateStatus:
        if self.get_active_task() is not None:
            return self.inspect()

        state = self._current_remote_refresh_state()
        if not force and not state.stale:
            return self.inspect()

        with package_mutation_lock():
            state = self._current_remote_refresh_state()
            if not force and not state.stale:
                return self.inspect()
            self._fetch_remote_refs()
        return self.inspect()

    def inspect_checkout(self) -> GitCheckoutState:
        project_root = self.project_root.resolve()
        is_git = self._git_success("rev-parse", "--is-inside-work-tree")
        if not is_git:
            return GitCheckoutState(
                project_root=project_root,
                is_git=False,
                blockers=(
                    _message(
                        "not_git_checkout",
                        "Project root is not a git checkout.",
                    ),
                ),
            )

        current_commit = self._git_output("rev-parse", "HEAD")
        branch = self._git_optional("symbolic-ref", "--quiet", "--short", "HEAD")
        is_detached = branch is None
        upstream_ref = (
            None
            if is_detached
            else self._git_optional(
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            )
        )
        upstream_commit = (
            self._git_optional("rev-parse", upstream_ref) if upstream_ref else None
        )
        ahead, behind = self._ahead_behind(upstream_ref)
        dirty_entries = self._dirty_entries()
        head_tags = tuple(self._git_lines("tag", "--points-at", "HEAD"))

        blockers: list[ProjectUpdateMessage] = []
        if is_detached:
            blockers.append(
                _message("detached_head", "Project checkout is in detached HEAD state.")
            )
        if not upstream_ref:
            blockers.append(
                _message(
                    "missing_upstream",
                    "Current branch has no configured upstream.",
                )
            )
        if dirty_entries:
            blockers.append(
                _message(
                    "dirty_worktree",
                    "Project worktree has local changes.",
                )
            )

        return GitCheckoutState(
            project_root=project_root,
            is_git=True,
            is_detached=is_detached,
            branch=branch,
            current_commit=current_commit,
            short_commit=current_commit[:8] if current_commit else None,
            upstream_ref=upstream_ref,
            upstream_commit=upstream_commit,
            ahead=ahead,
            behind=behind,
            dirty=bool(dirty_entries),
            dirty_entries=tuple(dirty_entries),
            head_tags=head_tags,
            blockers=tuple(blockers),
        )

    def list_release_candidates(
        self,
        checkout: GitCheckoutState | None = None,
    ) -> tuple[
        tuple[ProjectReleaseCandidate, ...],
        tuple[ProjectReleaseCandidate, ...],
    ]:
        checkout = checkout or self.inspect_checkout()
        if not checkout.is_git:
            return (), ()

        current_version = self._current_release_version(checkout)
        stable: list[ProjectReleaseCandidate] = []
        prerelease: list[ProjectReleaseCandidate] = []
        for tag in self._git_lines("tag", "--list"):
            semver = parse_semver_tag(tag)
            if semver is None:
                continue
            commit = self._git_optional("rev-list", "-n", "1", tag)
            if not commit:
                continue
            metadata = self._read_release_metadata(commit)
            candidate = self._release_candidate(
                tag=tag,
                semver=semver,
                commit=commit,
                metadata=metadata,
                checkout=checkout,
                current_version=current_version,
            )
            if semver.is_prerelease:
                prerelease.append(candidate)
            else:
                stable.append(candidate)

        return (
            tuple(
                sorted(
                    stable,
                    key=lambda candidate: _semver_sort_key(
                        parse_semver_tag(candidate.tag)
                    ),
                    reverse=True,
                )
            ),
            tuple(
                sorted(
                    prerelease,
                    key=lambda candidate: _semver_sort_key(
                        parse_semver_tag(candidate.tag)
                    ),
                    reverse=True,
                )
            ),
        )

    def create_plan(self, request: ProjectUpdatePlanRequest) -> ProjectUpdatePlan:
        if request.channel == "branch":
            return self._create_branch_plan(request)
        if request.channel == "release":
            return self._create_release_plan(request)
        return _blocked_plan(
            channel=request.channel,
            operation=request.operation or "update",
            blocker=_message("unsupported_channel", "Unsupported update channel."),
        )

    async def create_task(self, request: ProjectUpdatePlanRequest) -> ProjectUpdateTask:
        plan = self.create_plan(request)
        if not plan.allowed:
            messages = "; ".join(item.message for item in plan.blockers)
            raise _blocked_update_plan_error(messages)
        if self.get_active_task() is not None:
            raise _task_already_running_error()

        task_id = uuid4().hex
        task = ProjectUpdateTask(
            task_id=task_id,
            title=_task_title(plan),
            status="queued",
            logs="queued\n",
            created_at=_now(),
            channel=plan.channel,
            operation=plan.operation,
            target_ref=plan.target_ref,
            target_commit=plan.target_commit,
            target_tag=plan.target_tag,
            target_version=plan.target_version,
            current_phase="queued",
            current_phase_label="Queued",
            progress_percent=0,
            steps=(
                ProjectUpdateTaskStep(
                    phase="queued",
                    label="Queued",
                    status="running",
                    detail="Waiting for project update task execution.",
                    started_at=_now(),
                ),
            ),
        )
        self._tasks[task_id] = task
        self._active_task_id = task_id
        background_task = asyncio.create_task(self._run_task(task_id, plan))
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        return task

    def get_task(self, task_id: str) -> ProjectUpdateTask | None:
        return self._tasks.get(task_id)

    def get_active_task(self) -> ProjectUpdateTask | None:
        if self._active_task_id is None:
            return None
        task = self._tasks.get(self._active_task_id)
        if task is None or task.status not in {"queued", "running"}:
            return None
        return task

    def _build_branch_state(self, checkout: GitCheckoutState) -> BranchUpdateState:
        blockers = list(checkout.blockers)
        if checkout.is_git and checkout.upstream_ref and not checkout.dirty:
            if checkout.diverged:
                blockers.append(
                    _message(
                        "branch_diverged",
                        "Current branch has diverged from its upstream.",
                    )
                )
            elif checkout.ahead:
                blockers.append(
                    _message(
                        "branch_ahead",
                        "Current branch has local commits ahead of upstream.",
                    )
                )
            elif not checkout.behind:
                blockers.append(
                    _message(
                        "branch_up_to_date",
                        "Current branch is already up to date.",
                    )
                )
        return BranchUpdateState(
            available=not blockers,
            target_ref=checkout.upstream_ref,
            target_commit=checkout.upstream_commit,
            blockers=tuple(blockers),
        )

    def _create_branch_plan(
        self,
        request: ProjectUpdatePlanRequest,
    ) -> ProjectUpdatePlan:
        if request.operation == "rollback":
            return _blocked_plan(
                channel="branch",
                operation="rollback",
                blocker=_message(
                    "branch_rollback_unsupported",
                    "Branch channel supports fast-forward updates only.",
                ),
            )
        status = self.inspect()
        blockers = status.branch.blockers
        return ProjectUpdatePlan(
            channel="branch",
            operation="update",
            target_ref=status.branch.target_ref,
            target_commit=status.branch.target_commit,
            blockers=blockers,
            steps=(
                "Fetch upstream refs and tags",
                "Revalidate fast-forward target",
                "Merge upstream with --ff-only",
                "Sync backend dependencies",
                "Rebuild Web UI assets when available",
                "Require runtime restart",
            ),
            confirmation="update",
        )

    def _create_release_plan(
        self,
        request: ProjectUpdatePlanRequest,
    ) -> ProjectUpdatePlan:
        status = self.inspect()
        track = request.release_track or "stable"
        candidates = (
            status.stable_releases if track == "stable" else status.prerelease_releases
        )
        candidate = _select_release_candidate(candidates, request.target_tag)
        if candidate is None:
            return _blocked_plan(
                channel="release",
                operation=request.operation or "update",
                release_track=track,
                blocker=_message(
                    "release_target_unavailable",
                    "Requested release tag is not an available update target.",
                ),
            )
        operation = "rollback" if candidate.is_rollback else "update"
        if request.operation and request.operation != operation:
            return _blocked_plan(
                channel="release",
                operation=request.operation,
                release_track=track,
                target_tag=candidate.tag,
                target_commit=candidate.commit,
                blocker=_message(
                    "operation_mismatch",
                    "Requested operation does not match the selected target.",
                ),
            )

        blockers = [*_checkout_blockers(status.checkout), *candidate.blockers]
        warnings = [*candidate.warnings]
        confirmation = "rollback" if operation == "rollback" else "update"
        return ProjectUpdatePlan(
            channel="release",
            operation=operation,
            release_track=track,
            target_ref=f"refs/tags/{candidate.tag}",
            target_commit=candidate.commit,
            target_tag=candidate.tag,
            target_version=candidate.version,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            steps=(
                "Fetch release tags",
                "Revalidate selected release target",
                "Switch dedicated release deployment ref",
                "Sync backend dependencies",
                "Rebuild Web UI assets when available",
                "Require runtime restart",
            ),
            confirmation=confirmation,
        )

    async def _run_task(self, task_id: str, plan: ProjectUpdatePlan) -> None:
        try:
            await asyncio.to_thread(self._execute_plan_sync, task_id, plan)
        except Exception as exc:  # noqa: BLE001
            self._fail_task(task_id, exc)
        finally:
            self._active_task_id = None

    def _execute_plan_sync(self, task_id: str, plan: ProjectUpdatePlan) -> None:
        with package_mutation_lock():
            self._begin_task(task_id)
            self._run_step(
                task_id,
                "fetch",
                "Fetch refs and tags",
                lambda: self._fetch_for_plan(plan),
                progress=15,
            )
            self._run_step(
                task_id,
                "validate_target",
                "Validate update target",
                lambda: self._validate_plan_target(plan),
                progress=30,
            )
            self._run_step(
                task_id,
                "git_transition",
                "Apply git transition",
                lambda: self._apply_git_transition(plan),
                progress=50,
            )
            self._run_step(
                task_id,
                "dependency_sync",
                "Sync backend dependencies",
                self._sync_dependencies,
                progress=70,
            )
            self._run_step(
                task_id,
                "readiness",
                "Inspect runtime readiness",
                self._inspect_readiness,
                progress=96,
            )
            self._mark_task_succeeded(task_id, plan)

    def _begin_task(self, task_id: str) -> None:
        now = _now()
        self._finish_step(task_id, "queued", status="succeeded", finished_at=now)
        self._update_task(
            task_id,
            status="running",
            started_at=now,
            current_phase="running",
            current_phase_label="Running",
            logs=f"{self._tasks[task_id].logs}started\n",
        )

    def _run_step(
        self,
        task_id: str,
        phase: str,
        label: str,
        operation: "Callable[[], str | None]",
        *,
        progress: int,
    ) -> None:
        del progress
        self._start_step(task_id, phase, label)
        try:
            detail = operation()
        except Exception as exc:
            self._finish_step(task_id, phase, status="failed", detail=str(exc))
            raise
        self._finish_step(task_id, phase, status="succeeded", detail=detail)

    def _fetch_for_plan(self, plan: ProjectUpdatePlan) -> str:
        remote = self._remote_for_plan(plan)
        output = self._git_output_checked("fetch", "--tags", "--prune", remote)
        return output or f"Fetched {remote}."

    def _validate_plan_target(self, plan: ProjectUpdatePlan) -> str:
        next_plan = self.create_plan(
            ProjectUpdatePlanRequest(
                channel=plan.channel,
                release_track=plan.release_track,
                target_tag=plan.target_tag,
                operation=plan.operation,
            )
        )
        if not next_plan.allowed:
            messages = "; ".join(item.message for item in next_plan.blockers)
            raise _blocked_update_target_error(messages)
        if next_plan.target_commit != plan.target_commit:
            raise _target_changed_after_fetch_error()
        return "Target is still valid."

    def _apply_git_transition(self, plan: ProjectUpdatePlan) -> str:
        if plan.channel == "branch":
            if not plan.target_ref:
                raise _missing_branch_target_error()
            output = self._git_output_checked("merge", "--ff-only", plan.target_ref)
            return output or f"Fast-forwarded to {plan.target_ref}."
        if not plan.target_commit:
            raise _missing_release_target_error()
        output = self._git_output_checked(
            "switch",
            "-C",
            _DEPLOY_BRANCH,
            plan.target_commit,
        )
        return output or f"Switched {_DEPLOY_BRANCH} to {plan.target_commit[:8]}."

    def _sync_dependencies(self) -> str:
        environment_service.sync_main_project()
        return "Backend dependencies synced."

    def _inspect_readiness(self) -> str:
        inspection = inspect_database(self.project_root)
        return f"Database schema status: {inspection.schema.status}."

    def _mark_task_succeeded(self, task_id: str, plan: ProjectUpdatePlan) -> None:
        finished_at = _now()
        self._update_task(
            task_id,
            status="succeeded",
            finished_at=finished_at,
            current_phase="succeeded",
            current_phase_label="Succeeded",
            progress_percent=100,
            restart_required=True,
            result={
                "channel": plan.channel,
                "operation": plan.operation,
                "target_ref": plan.target_ref,
                "target_commit": plan.target_commit,
                "target_tag": plan.target_tag,
                "target_version": plan.target_version,
                "restart_required": True,
            },
            logs=f"{self._tasks[task_id].logs}project update succeeded\n",
        )
        self._start_step(
            task_id,
            "succeeded",
            "Succeeded",
            status="succeeded",
            detail="Project update completed. Restart is required.",
            started_at=finished_at,
            finished_at=finished_at,
        )

    def _fail_task(self, task_id: str, exc: Exception) -> None:
        task = self._tasks.get(task_id)
        if task is None or task.status == "failed":
            return
        error = sanitize_output(str(exc).strip() or exc.__class__.__name__)
        self._update_task(
            task_id,
            status="failed",
            finished_at=_now(),
            current_phase="failed",
            current_phase_label="Failed",
            error=error,
            diagnostics=(
                *task.diagnostics,
                {"phase": task.current_phase or "failed", "message": error},
            ),
            logs=f"{task.logs}project update failed\n{error}\n",
        )

    def _start_step(  # noqa: PLR0913
        self,
        task_id: str,
        phase: str,
        label: str,
        *,
        status: str = "running",
        detail: str | None = None,
        command: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        started = started_at or _now()
        task = self._tasks[task_id]
        self._update_task(
            task_id,
            current_phase=phase,
            current_phase_label=label,
            steps=(
                *task.steps,
                ProjectUpdateTaskStep(
                    phase=phase,
                    label=label,
                    status=status,
                    detail=detail,
                    command=command,
                    started_at=started,
                    finished_at=finished_at,
                ),
            ),
            logs=f"{task.logs}{label}\n",
        )

    def _finish_step(
        self,
        task_id: str,
        phase: str,
        *,
        status: str,
        detail: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        task = self._tasks[task_id]
        steps = list(task.steps)
        for index in range(len(steps) - 1, -1, -1):
            step = steps[index]
            if step.phase == phase and step.finished_at is None:
                steps[index] = replace(
                    step,
                    status=status,
                    detail=detail or step.detail,
                    finished_at=finished_at or _now(),
                )
                self._update_task(task_id, steps=tuple(steps))
                return

    def _update_task(self, task_id: str, **changes: object) -> None:
        self._tasks[task_id] = replace(self._tasks[task_id], **changes)

    def _release_candidate(  # noqa: PLR0913
        self,
        *,
        tag: str,
        semver: SemverTag,
        commit: str,
        metadata: ProjectReleaseMetadata,
        checkout: GitCheckoutState,
        current_version: SemverTag | None,
    ) -> ProjectReleaseCandidate:
        warnings: list[ProjectUpdateMessage] = []
        blockers: list[ProjectUpdateMessage] = []
        if not metadata.available:
            warnings.append(
                _message(
                    "release_metadata_missing",
                    "Release metadata is unavailable for this tag.",
                )
            )

        database = inspect_database(self.project_root)
        schema_version = database.schema.schema_version
        if schema_version is not None:
            if (
                metadata.database_schema_min is not None
                and schema_version < metadata.database_schema_min
            ):
                blockers.append(
                    _message(
                        "database_schema_too_old",
                        "Current database schema is older than the target supports.",
                    )
                )
            if (
                metadata.database_schema_max is not None
                and schema_version > metadata.database_schema_max
            ):
                blockers.append(
                    _message(
                        "database_schema_too_new",
                        "Current database schema is newer than the target supports.",
                    )
                )
        if metadata.requires_python:
            python_message = _python_requirement_blocker(metadata.requires_python)
            if python_message is not None:
                blockers.append(python_message)

        is_current = checkout.current_commit == commit or tag in checkout.head_tags
        is_rollback = (
            current_version is not None and _compare_semver(semver, current_version) < 0
        )
        return ProjectReleaseCandidate(
            tag=tag,
            version=semver.public_version,
            commit=commit,
            prerelease=semver.is_prerelease,
            metadata=metadata,
            is_current=is_current,
            is_rollback=is_rollback,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    def _current_release_version(self, checkout: GitCheckoutState) -> SemverTag | None:
        tags = list(checkout.head_tags)
        if not tags and checkout.is_git:
            described = self._git_optional("describe", "--tags", "--abbrev=0")
            if described:
                tags.append(described)
        versions = [version for tag in tags if (version := parse_semver_tag(tag))]
        if not versions:
            return None
        return max(versions, key=_semver_sort_key)

    def _read_release_metadata(self, commit: str) -> ProjectReleaseMetadata:
        pyproject = self._git_optional("show", f"{commit}:pyproject.toml")
        if not pyproject:
            return ProjectReleaseMetadata()

        try:
            data = tomlkit.parse(pyproject)
        except ValueError:
            return ProjectReleaseMetadata()

        project = _mapping_or_empty(data.get("project"))
        tool = _mapping_or_empty(data.get("tool"))
        apeiria = _mapping_or_empty(tool.get("apeiria"))
        release = _mapping_or_empty(apeiria.get("release"))
        return ProjectReleaseMetadata(
            version=_string_or_none(release.get("version") or project.get("version")),
            database_schema_min=_int_or_none(release.get("database_schema_min")),
            database_schema_max=_int_or_none(release.get("database_schema_max")),
            requires_python=_string_or_none(
                release.get("requires_python") or project.get("requires-python")
            ),
            source="pyproject.toml",
            available=bool(release),
        )

    def _remote_for_plan(self, plan: ProjectUpdatePlan) -> str:
        if plan.channel == "branch":
            checkout = self.inspect_checkout()
            if not checkout.upstream_ref or "/" not in checkout.upstream_ref:
                raise _missing_branch_remote_error()
            return checkout.upstream_ref.split("/", 1)[0]
        return "origin"

    def _fetch_remote_refs(self) -> None:
        now = datetime.now(timezone.utc)
        remotes = self._remote_names_for_refresh()
        if not remotes:
            self._remote_refresh = ProjectUpdateRemoteRefreshState(
                ttl_seconds=_REMOTE_REFRESH_TTL_SECONDS,
                stale=True,
                last_checked_at=_format_datetime(now),
                next_check_after=_format_datetime(
                    now + timedelta(seconds=_REMOTE_REFRESH_ERROR_BACKOFF_SECONDS)
                ),
                last_error_at=_format_datetime(now),
                last_error="No git remote is configured.",
            )
            return

        try:
            for remote in remotes:
                self._git_output_checked("fetch", "--tags", "--prune", remote)
        except Exception as exc:
            self._remote_refresh = ProjectUpdateRemoteRefreshState(
                ttl_seconds=_REMOTE_REFRESH_TTL_SECONDS,
                stale=True,
                last_checked_at=_format_datetime(now),
                last_success_at=self._remote_refresh.last_success_at,
                next_check_after=_format_datetime(
                    now + timedelta(seconds=_REMOTE_REFRESH_ERROR_BACKOFF_SECONDS)
                ),
                last_error_at=_format_datetime(now),
                last_error=sanitize_output(str(exc)),
                remotes=remotes,
            )
            raise

        self._remote_refresh = ProjectUpdateRemoteRefreshState(
            ttl_seconds=_REMOTE_REFRESH_TTL_SECONDS,
            stale=False,
            last_checked_at=_format_datetime(now),
            last_success_at=_format_datetime(now),
            next_check_after=_format_datetime(
                now + timedelta(seconds=_REMOTE_REFRESH_TTL_SECONDS)
            ),
            remotes=remotes,
        )

    def _remote_names_for_refresh(self) -> tuple[str, ...]:
        if not self._git_success("rev-parse", "--is-inside-work-tree"):
            return ()

        names: list[str] = []
        checkout = self.inspect_checkout()
        if checkout.upstream_ref and "/" in checkout.upstream_ref:
            names.append(checkout.upstream_ref.split("/", 1)[0])
        remote_names = self._git_lines("remote")
        if "origin" in remote_names:
            names.append("origin")
        elif remote_names:
            names.append(remote_names[0])
        return tuple(dict.fromkeys(name for name in names if name))

    def _current_remote_refresh_state(self) -> ProjectUpdateRemoteRefreshState:
        last_success_at = _parse_datetime(self._remote_refresh.last_success_at)
        stale = last_success_at is None or datetime.now(
            timezone.utc
        ) >= last_success_at + timedelta(seconds=_REMOTE_REFRESH_TTL_SECONDS)
        return replace(self._remote_refresh, stale=stale)

    def _git_success(self, *args: str) -> bool:
        return self._run_git(args).returncode == 0

    def _git_output(self, *args: str) -> str:
        result = self._run_git(args)
        if result.returncode != 0:
            raise GitCommandError(_command_error(args, result))
        return result.stdout.strip()

    def _git_output_checked(self, *args: str) -> str:
        result = self._run_git(args)
        if result.returncode != 0:
            raise GitCommandError(_command_error(args, result))
        return sanitize_output(_bounded_output(result.stdout, result.stderr)).strip()

    def _git_optional(self, *args: str) -> str | None:
        result = self._run_git(args)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def _git_lines(self, *args: str) -> list[str]:
        result = self._run_git(args)
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _run_git(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return subprocess.run(
            ["git", *args],
            cwd=self.project_root,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def _ahead_behind(self, upstream_ref: str | None) -> tuple[int | None, int | None]:
        if not upstream_ref:
            return (None, None)
        counts = self._git_optional(
            "rev-list",
            "--left-right",
            "--count",
            "HEAD...@{upstream}",
        )
        if not counts:
            return (None, None)
        parts = counts.split()
        if len(parts) != _AHEAD_BEHIND_PART_COUNT:
            return (None, None)
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return (None, None)

    def _dirty_entries(self) -> list[str]:
        return self._git_lines("status", "--porcelain=v1")


project_update_service = ProjectUpdateService()
