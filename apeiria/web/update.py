from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from nonebot.log import logger

from apeiria.web.auth import verify_token

router = APIRouter(prefix="/api/update", dependencies=[Depends(verify_token)])

_DIRTY_BLOCK_MESSAGE = "工作区存在未提交的变更，请先处理后重试"


async def _run_git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    if cwd is None:
        cwd = Path.cwd()
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode(errors="replace").strip(),
        stderr.decode(errors="replace").strip(),
    )


async def _run_stream(*args: str, cwd: Path | None = None) -> AsyncIterator[str]:
    if cwd is None:
        cwd = Path.cwd()
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    if proc.stdout is None:
        return
    async for line in proc.stdout:
        yield line.decode(errors="replace").rstrip()
    await proc.wait()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _branch_list(output: str) -> list[str]:
    branches: list[str] = []
    for raw in output.splitlines():
        stripped = raw.strip()
        if not stripped or "->" in stripped:
            continue
        if stripped.startswith("origin/"):
            branches.append(stripped[len("origin/") :])
        else:
            branches.append(stripped)
    return sorted(set(branches))


@router.get("/status")
async def update_status() -> JSONResponse:
    rc, branch, _ = await _run_git("branch", "--show-current")
    if rc != 0 or not branch:
        raise HTTPException(status_code=500, detail="无法获取当前分支")

    _, commit_hash, _ = await _run_git("rev-parse", "--short", "HEAD")
    _, commit_message, _ = await _run_git("log", "-1", "--format=%s")

    _, dirty_output, _ = await _run_git("status", "--porcelain")
    is_dirty = bool(dirty_output)
    dirty_files = dirty_output.splitlines() if dirty_output else []

    _, branches_output, _ = await _run_git("branch", "-r")
    available_branches = _branch_list(branches_output)

    return JSONResponse(
        content={
            "branch": branch,
            "commit_hash": commit_hash,
            "commit_message": commit_message,
            "is_dirty": is_dirty,
            "dirty_files": dirty_files,
            "available_branches": available_branches,
        }
    )


@router.get("/preview/{branch}")
async def update_preview(branch: str) -> JSONResponse:
    rc, _, stderr = await _run_git("fetch", "origin", branch)
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"Fetch 失败: {stderr}")

    remote_ref = f"origin/{branch}"
    rc, _, stderr = await _run_git("rev-parse", "--short", remote_ref)
    if rc != 0:
        raise HTTPException(status_code=404, detail=f"远端不存在分支 '{branch}'")

    _, remote_hash, _ = await _run_git("rev-parse", "--short", remote_ref)
    _, remote_msg, _ = await _run_git("log", "-1", "--format=%s", remote_ref)

    _, behind_str, _ = await _run_git("rev-list", "--count", f"HEAD..{remote_ref}")
    commits_behind = int(behind_str) if behind_str else 0

    return JSONResponse(
        content={
            "branch": branch,
            "remote_commit_hash": remote_hash,
            "remote_commit_message": remote_msg,
            "commits_behind": commits_behind,
        }
    )


async def _do_rollback(
    original_branch: str,
    original_commit: str,
    cwd: Path,
) -> None:
    logger.warning("Rolling back to {} ({})", original_branch, original_commit[:7])
    await _run_git("checkout", original_branch, cwd=cwd)
    await _run_git("reset", "--hard", original_commit, cwd=cwd)
    logger.info("Rollback complete")


async def _execute_update(branch: str) -> AsyncIterator[str]:  # noqa: C901, PLR0912
    project_root = Path.cwd()

    rc, dirty, _ = await _run_git("status", "--porcelain")
    if rc == 0 and dirty:
        yield _sse({"stage": "error", "line": _DIRTY_BLOCK_MESSAGE})
        return

    _, original_commit, _ = await _run_git("rev-parse", "HEAD")
    _, original_branch, _ = await _run_git("branch", "--show-current")
    logger.info(
        "Starting update to branch '{}' from {} ({})",
        branch,
        original_branch,
        original_commit[:7],
    )

    yield _sse({"stage": "checkout", "line": f"$ git checkout {branch}"})
    rc2, out, err = await _run_git("checkout", branch)
    if rc2 != 0:
        err_stderr = await _run_git("checkout", "-b", branch, f"origin/{branch}")
        if err_stderr[0] != 0:
            yield _sse({"stage": "error", "line": f"Checkout 失败: {err_stderr[2]}"})
            return
        out = f"Switched to a new branch '{branch}'"
    for line in out.splitlines():
        if line.strip():
            yield _sse({"stage": "checkout", "line": line})
    for line in err.splitlines():
        if line.strip():
            yield _sse({"stage": "checkout", "line": line})

    yield _sse({"stage": "pull", "line": f"$ git fetch origin {branch}"})
    rc3, _, fetch_err = await _run_git("fetch", "origin", branch)
    if rc3 != 0:
        await _do_rollback(original_branch, original_commit, project_root)
        yield _sse({"stage": "error", "line": f"Fetch 失败: {fetch_err}"})
        return

    yield _sse({"stage": "pull", "line": f"$ git reset --hard origin/{branch}"})
    rc4, reset_out, reset_err = await _run_git("reset", "--hard", f"origin/{branch}")
    for line in reset_out.splitlines():
        if line.strip():
            yield _sse({"stage": "pull", "line": line})
    for line in reset_err.splitlines():
        if line.strip():
            yield _sse({"stage": "pull", "line": line})
    if rc4 != 0:
        await _do_rollback(original_branch, original_commit, project_root)
        yield _sse({"stage": "error", "line": f"Reset 失败: {reset_err}"})
        return

    uv = shutil.which("uv")
    if uv is None:
        await _do_rollback(original_branch, original_commit, project_root)
        yield _sse({"stage": "error", "line": "系统中未找到 uv 命令"})
        return

    yield _sse({"stage": "sync", "line": "$ uv sync"})
    async for line in _run_stream(uv, "sync", cwd=project_root):
        yield _sse({"stage": "sync", "line": line})

    yield _sse({"stage": "done", "line": "更新完成，即将重启..."})
    logger.success("Git update to '{}' completed. Restarting...", branch)

    from apeiria.utils.restart import graceful_restart

    await asyncio.sleep(0.8)
    await graceful_restart()


@router.post("/execute")
async def update_execute(request: Request) -> StreamingResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=400, detail="请求体无效 JSON") from err

    branch = body.get("branch")
    if not branch or not isinstance(branch, str):
        raise HTTPException(status_code=400, detail="缺少或无效的 'branch' 字段")

    return StreamingResponse(
        _execute_update(branch),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
