from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.system.project_update import (
    ProjectUpdateMessage,
    ProjectUpdatePlanRequest,
    ProjectUpdateService,
    parse_semver_tag,
    sanitize_output,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def test_inspect_clean_checkout_reports_upstream(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    service = ProjectUpdateService(project_root=repo)

    checkout = service.inspect_checkout()

    assert checkout.is_git is True
    assert checkout.branch == "main"
    assert checkout.upstream_ref == "origin/main"
    assert checkout.ahead == 0
    assert checkout.behind == 0
    assert checkout.dirty is False


def test_inspect_missing_upstream_blocks_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _write(repo / "README.md", "hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")

    service = ProjectUpdateService(project_root=repo)
    status = service.inspect()

    assert _codes(status.checkout.blockers) == {"missing_upstream"}
    assert "missing_upstream" in _codes(status.branch.blockers)


def test_inspect_detached_head_blocks(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    commit = _git_output(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", commit)

    checkout = ProjectUpdateService(project_root=repo).inspect_checkout()

    assert checkout.is_detached is True
    assert "detached_head" in _codes(checkout.blockers)


def test_inspect_non_git_project_blocks(tmp_path: Path) -> None:
    status = ProjectUpdateService(project_root=tmp_path).inspect()

    assert status.checkout.is_git is False
    assert _codes(status.checkout.blockers) == {"not_git_checkout"}


def test_inspect_dirty_worktree_blocks_update(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    _write(repo / "README.md", "changed\n")

    status = ProjectUpdateService(project_root=repo).inspect()

    assert status.checkout.dirty is True
    assert "dirty_worktree" in _codes(status.branch.blockers)


def test_branch_plan_allows_fast_forward(tmp_path: Path) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    _commit_remote_change(remote)
    _git(repo, "fetch", "origin")

    plan = ProjectUpdateService(project_root=repo).create_plan(
        ProjectUpdatePlanRequest(channel="branch")
    )

    assert plan.allowed is True
    assert plan.target_ref == "origin/main"
    assert plan.operation == "update"


def test_branch_plan_blocks_ahead_branch(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    _write(repo / "local.txt", "local\n")
    _git(repo, "add", "local.txt")
    _git(repo, "commit", "-m", "local")

    plan = ProjectUpdateService(project_root=repo).create_plan(
        ProjectUpdatePlanRequest(channel="branch")
    )

    assert plan.allowed is False
    assert "branch_ahead" in _codes(plan.blockers)


def test_branch_plan_blocks_diverged_branch(tmp_path: Path) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    _commit_remote_change(remote)
    _write(repo / "local.txt", "local\n")
    _git(repo, "add", "local.txt")
    _git(repo, "commit", "-m", "local")
    _git(repo, "fetch", "origin")

    plan = ProjectUpdateService(project_root=repo).create_plan(
        ProjectUpdatePlanRequest(channel="branch")
    )

    assert plan.allowed is False
    assert "branch_diverged" in _codes(plan.blockers)


def test_release_candidates_split_stable_and_prerelease(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    _tag(repo, "v1.0.0")
    _tag(repo, "v1.1.0-beta.1")
    _tag(repo, "not-a-version")

    status = ProjectUpdateService(project_root=repo).inspect()

    assert [item.tag for item in status.stable_releases] == ["v1.0.0"]
    assert [item.tag for item in status.prerelease_releases] == ["v1.1.0-beta.1"]


def test_prerelease_plan_does_not_leak_into_stable_default(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    _tag(repo, "v1.0.0")
    _tag(repo, "v2.0.0-rc.1")

    service = ProjectUpdateService(project_root=repo)
    stable_plan = service.create_plan(
        ProjectUpdatePlanRequest(channel="release", release_track="stable")
    )
    prerelease_plan = service.create_plan(
        ProjectUpdatePlanRequest(channel="release", release_track="prerelease")
    )

    assert stable_plan.target_tag == "v1.0.0"
    assert prerelease_plan.target_tag == "v2.0.0-rc.1"


def test_release_rollback_plan_requires_rollback_confirmation(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    _tag(repo, "v1.0.0")
    _write(repo / "feature.txt", "new\n")
    _git(repo, "add", "feature.txt")
    _git(repo, "commit", "-m", "feature")
    _tag(repo, "v2.0.0")

    plan = ProjectUpdateService(project_root=repo).create_plan(
        ProjectUpdatePlanRequest(
            channel="release",
            release_track="stable",
            target_tag="v1.0.0",
        )
    )

    assert plan.operation == "rollback"
    assert plan.confirmation == "rollback"


def test_release_metadata_blocks_incompatible_database(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    ApeiriaDatabase(project_root=repo).ensure_ready()
    _write(
        repo / "pyproject.toml",
        "\n".join(
            [
                "[project]",
                'name = "demo"',
                'version = "1.0.0"',
                "",
                "[tool.apeiria.release]",
                "database_schema_min = 100",
                "database_schema_max = 200",
                (
                    'requires_python = "'
                    f'>={sys.version_info.major}.{sys.version_info.minor}"'
                ),
            ]
        )
        + "\n",
    )
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-m", "release metadata")
    _tag(repo, "v1.0.0")

    candidate = ProjectUpdateService(project_root=repo).inspect().stable_releases[0]

    assert "database_schema_too_old" in _codes(candidate.blockers)
    assert candidate.metadata.available is True


def test_release_missing_metadata_warns(tmp_path: Path) -> None:
    repo, _remote = _create_repo_with_upstream(tmp_path)
    _tag(repo, "v1.0.0")

    candidate = ProjectUpdateService(project_root=repo).inspect().stable_releases[0]

    assert "release_metadata_missing" in _codes(candidate.warnings)


def test_refresh_remote_refs_fetches_remote_tags(
    tmp_path: Path,
) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    service = ProjectUpdateService(project_root=repo)

    _tag_remote_change(remote, "v1.0.0")

    assert service.inspect().stable_releases == ()

    status = service.refresh_remote_refs(force=True)

    assert [item.tag for item in status.stable_releases] == ["v1.0.0"]
    assert status.remote_refresh.stale is False
    assert status.remote_refresh.last_success_at is not None
    assert status.remote_refresh.remotes == ("origin",)


def test_refresh_remote_refs_uses_ttl_cache(
    tmp_path: Path,
) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    service = ProjectUpdateService(project_root=repo)

    service.refresh_remote_refs(force=True)
    checked_at = service.inspect().remote_refresh.last_checked_at
    _tag_remote_change(remote, "v1.0.0")

    cached_status = service.refresh_remote_refs()

    assert cached_status.stable_releases == ()
    assert cached_status.remote_refresh.last_checked_at == checked_at
    assert cached_status.remote_refresh.stale is False


def test_semver_parser_supports_prerelease() -> None:
    version = parse_semver_tag("v1.2.3-rc.1")

    assert version is not None
    assert version.is_prerelease is True
    assert version.public_version == "1.2.3-rc.1"


def test_sanitize_output_masks_credentials() -> None:
    assert (
        sanitize_output(
            "https://user:pass@example.test/repo.git token=abc password=def"
        )
        == "https://***@example.test/repo.git token=*** password=***"
    )


def test_update_task_success_reports_restart_required(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    _commit_remote_change(remote)
    _git(repo, "fetch", "origin")
    service = ProjectUpdateService(project_root=repo)

    monkeypatch.setattr(
        "apeiria.system.project_update.environment_service",
        _fake_environment_service(),
    )

    async def scenario() -> None:
        task = await service.create_task(ProjectUpdatePlanRequest(channel="branch"))
        await _wait_for_task(service, task.task_id)
        completed = service.get_task(task.task_id)
        assert completed is not None
        assert completed.status == "succeeded"
        assert completed.restart_required is True
        assert completed.result["restart_required"] is True
        assert {step.phase for step in completed.steps} >= {
            "fetch",
            "validate_target",
            "git_transition",
            "dependency_sync",
            "readiness",
        }

    import asyncio

    asyncio.run(scenario())


def test_update_task_rejects_concurrent_task(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    _commit_remote_change(remote)
    _git(repo, "fetch", "origin")
    service = ProjectUpdateService(project_root=repo)

    monkeypatch.setattr(
        "apeiria.system.project_update.environment_service",
        _slow_environment_service(),
    )

    async def scenario() -> None:
        task = await service.create_task(ProjectUpdatePlanRequest(channel="branch"))
        try:
            try:
                await service.create_task(ProjectUpdatePlanRequest(channel="branch"))
            except Exception as exc:  # noqa: BLE001
                assert "already running" in str(exc)
            else:
                raise _concurrent_task_accepted_error()
        finally:
            await _wait_for_task(service, task.task_id)

    import asyncio

    asyncio.run(scenario())


def test_update_task_failure_keeps_sanitized_diagnostics(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    repo, remote = _create_repo_with_upstream(tmp_path)
    _commit_remote_change(remote)
    _git(repo, "fetch", "origin")
    service = ProjectUpdateService(project_root=repo)

    monkeypatch.setattr(
        "apeiria.system.project_update.environment_service",
        _failing_environment_service(
            "https://user:pass@example.test/repo.git token=abc"
        ),
    )

    async def scenario() -> None:
        task = await service.create_task(ProjectUpdatePlanRequest(channel="branch"))
        await _wait_for_task(service, task.task_id)
        completed = service.get_task(task.task_id)
        assert completed is not None
        assert completed.status == "failed"
        assert "user:pass" not in completed.logs
        assert "token=abc" not in completed.logs
        assert "https://***@example.test/repo.git" in completed.logs
        assert "token=***" in completed.logs

    import asyncio

    asyncio.run(scenario())


def _create_repo_with_upstream(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(tmp_path, "clone", str(remote), str(repo))
    _git(repo, "switch", "-c", "main")
    _write(repo / "README.md", "hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "push", "-u", "origin", "main")
    return repo, remote


def _commit_remote_change(remote: Path) -> None:
    work = remote.parent / "remote-work"
    _git(remote.parent, "clone", str(remote), str(work))
    _git(work, "switch", "main")
    _write(work / "remote.txt", "remote\n")
    _git(work, "add", "remote.txt")
    _git(work, "commit", "-m", "remote")
    _git(work, "push", "origin", "main")


def _tag_remote_change(remote: Path, tag_name: str) -> None:
    work = remote.parent / f"remote-tag-{tag_name.replace('/', '-')}"
    _git(remote.parent, "clone", str(remote), str(work))
    _git(work, "switch", "main")
    _git(work, "tag", tag_name)
    _git(work, "push", "origin", tag_name)


def _tag(repo: Path, name: str) -> None:
    _git(repo, "tag", name)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _codes(messages: "Iterable[ProjectUpdateMessage]") -> set[str]:
    return {message.code for message in messages}


def _git(cwd: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os_environ_for_git(),
        },
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _git_output(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os_environ_for_git(),
        },
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def os_environ_for_git() -> dict[str, str]:
    import os

    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.test",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.test",
    }


def _fake_environment_service() -> object:
    return SimpleNamespace(
        sync_main_project=lambda: None,
    )


def _slow_environment_service() -> object:
    def sync_main_project() -> None:
        import time

        time.sleep(0.1)

    return SimpleNamespace(
        sync_main_project=sync_main_project,
    )


def _failing_environment_service(message: str) -> object:
    def sync_main_project() -> None:
        raise RuntimeError(message)

    return SimpleNamespace(
        sync_main_project=sync_main_project,
    )


async def _wait_for_task(
    service: ProjectUpdateService,
    task_id: str,
    *,
    attempts: int = 50,
) -> None:
    import asyncio

    for _ in range(attempts):
        task = service.get_task(task_id)
        if task is not None and task.status in {"succeeded", "failed"}:
            return
        await asyncio.sleep(0.02)
    raise _task_timeout_error()


def _concurrent_task_accepted_error() -> AssertionError:
    return AssertionError("concurrent task was accepted")


def _task_timeout_error() -> AssertionError:
    return AssertionError("task did not finish")
