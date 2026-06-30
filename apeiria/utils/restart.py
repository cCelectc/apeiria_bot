from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import time
from pathlib import Path

from nonebot.log import logger

_TERM_GRACE_SECONDS = 2.0
_POLL_INTERVAL = 0.1


def _read_ppid(pid: int) -> int | None:
    try:
        content = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    rparen = content.rfind(")")
    if rparen == -1:
        return None
    fields = content[rparen + 2 :].split()
    if len(fields) < 2:  # noqa: PLR2004
        return None
    try:
        return int(fields[1])
    except ValueError:
        return None


def _build_proc_tree() -> dict[int, list[int]]:
    proc = Path("/proc")
    children: dict[int, list[int]] = {}
    if not proc.is_dir():
        return children
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        ppid = _read_ppid(pid)
        if ppid is None:
            continue
        children.setdefault(ppid, []).append(pid)
    return children


def _collect_descendants(children: dict[int, list[int]], root: int) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    queue = list(children.get(root, []))
    while queue:
        pid = queue.pop()
        if pid in seen:
            continue
        seen.add(pid)
        result.append(pid)
        queue.extend(children.get(pid, []))
    return result


def descendant_pids(root_pid: int) -> list[int]:
    """返回 *root_pid* 进程的全部后代 PID（Linux，扫 /proc）。

    `/proc` 不可用或解析失败时返回空列表，绝不抛出。
    """
    return _collect_descendants(_build_proc_tree(), root_pid)


def _signal_pid(pid: int, sig: int) -> None:
    with contextlib.suppress(OSError):
        os.kill(pid, sig)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


async def _terminate_descendants() -> None:
    """SIGTERM → 宽限 → SIGKILL 杀掉当前进程的全部后代（兜底浏览器进程）。

    Windows 上"杀子树但不杀自身"非平凡，此处不处理（见 tasks Gaps）。
    """
    if sys.platform == "win32":
        return
    pids = descendant_pids(os.getpid())
    if not pids:
        return
    logger.info("Terminating {} descendant process(es) before restart", len(pids))
    for pid in pids:
        _signal_pid(pid, signal.SIGTERM)
    deadline = time.monotonic() + _TERM_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not any(_pid_alive(pid) for pid in pids):
            return
        await asyncio.sleep(_POLL_INTERVAL)
    for pid in pids:
        if _pid_alive(pid):
            _signal_pid(pid, signal.SIGKILL)


async def _shutdown_render_safe() -> None:
    try:
        from nonebot_plugin_htmlrender import shutdown_render

        await shutdown_render()
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).debug("shutdown_render skipped during restart")


async def _close_db_safe() -> None:
    try:
        from apeiria.db.engine import close_db

        await close_db()
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).debug("close_db failed during restart")


def _exec_restart() -> None:
    with contextlib.suppress(OSError):
        sys.stdout.flush()
        sys.stderr.flush()

    if sys.platform == "win32":
        import subprocess

        subprocess.Popen(
            [sys.executable, *sys.argv],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
        )
        os._exit(0)
    else:
        os.execv(sys.executable, [sys.executable, *sys.argv])


async def graceful_restart() -> None:
    """优雅清理后重启：关浏览器树 → 关库 → 杀残留后代 → 替换进程映像。

    每步独立容错；调用方负责在调用前发送重启通知。该函数不会返回。
    """
    logger.info("Graceful restart: cleaning up before re-exec")
    await _shutdown_render_safe()
    await _close_db_safe()
    await _terminate_descendants()
    _exec_restart()
