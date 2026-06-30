from __future__ import annotations

from pathlib import Path


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
