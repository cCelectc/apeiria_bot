from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from nonebot.log import logger

from apeiria.ai.tools.builtin.acp import cancel_acp_tool
from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult

_SANDBOX_BASE = Path("data/acp_workspaces")
_active_tasks: dict[str, asyncio.Task[None]] = {}
_task_queue: dict[str, list[dict[str, Any]]] = {}


async def register_acp_tools() -> int:
    from sqlalchemy import select

    from apeiria.db.engine import get_session
    from apeiria.db.models.infrastructure import ACPAgent

    async with get_session() as db:
        agents = list(
            (await db.execute(select(ACPAgent).where(ACPAgent.enabled == 1)))
            .scalars()
            .all()
        )

    for agent in agents:
        args = json.loads(agent.args_json) if agent.args_json else []
        env = json.loads(agent.env_json) if agent.env_json else None
        tool = _build_acp_tool(
            agent_name=agent.name,
            command=agent.command,
            args=args,
            env=env,
            workspace_config=agent.workspace,
        )
        register_tool(tool)

    if agents:
        register_tool(cancel_acp_tool)

    return len(agents)


def _build_acp_tool(
    agent_name: str,
    command: str,
    args: list[str],
    env: dict[str, str] | None,
    workspace_config: str | None,
) -> Tool:
    async def execute(
        *,
        task: str,
        _ctx: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> ToolResult:
        session_id = (_ctx or {}).get("session_id", "unknown")
        user_id = (_ctx or {}).get("user_id")

        denied = _check_acp_permission(_ctx, user_id)
        if denied is not None:
            return denied

        if session_id in _active_tasks and not _active_tasks[session_id].done():
            return _enqueue_task(session_id, task, agent_name)

        task_id = str(uuid.uuid4())

        if workspace_config:
            workspace = workspace_config
        else:
            workspace = str(_SANDBOX_BASE / f"{session_id}_{task_id}")
            _ensure_dir(workspace)

        bg = asyncio.create_task(
            _run_acp_background(
                agent_name=agent_name,
                command=command,
                args=args,
                env=env,
                task_description=task,
                workspace=workspace,
                session_id=session_id,
                is_sandbox=workspace_config is None,
            )
        )
        _active_tasks[session_id] = bg

        return ToolResult(
            success=True,
            content=json.dumps({"status": "accepted", "task_id": task_id}),
        )

    return Tool(
        name=f"acp_{agent_name}",
        description=(
            f"Delegate a task to the '{agent_name}' agent."
            " The task runs asynchronously and results will"
            " be injected into the conversation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": ("Description of the task to delegate"),
                },
            },
            "required": ["task"],
        },
        execute=execute,
    )


def _check_acp_permission(
    ctx: dict[str, Any] | None, user_id: Any
) -> ToolResult | None:
    settings = (ctx or {}).get("settings")
    if settings and settings.acp_access_mode == "superuser_only":
        superusers = (ctx or {}).get("superusers", set())
        if user_id and user_id not in superusers:
            return ToolResult(
                success=False,
                error="ACP access denied: superuser only",
            )
    return None


def _enqueue_task(session_id: str, task: str, agent_name: str) -> ToolResult:
    _task_queue.setdefault(session_id, []).append(
        {"task": task, "agent_name": agent_name}
    )
    pos = len(_task_queue[session_id])
    return ToolResult(
        success=True,
        content=json.dumps({"status": "queued", "position": pos}),
    )


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _cleanup_sandbox(workspace: str) -> None:
    sandbox_path = Path(workspace)
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path, ignore_errors=True)


async def _inject_acp_message(session_id: str, content: str) -> None:
    try:
        from apeiria.conversation.service import (
            append_message,
        )

        await append_message(session_id, "system", content=content)
    except Exception:  # noqa: BLE001
        logger.debug("ACP message inject failed", exc_info=True)


async def _run_acp_background(  # noqa: PLR0913
    *,
    agent_name: str,
    command: str,
    args: list[str],
    env: dict[str, str] | None,
    task_description: str,
    workspace: str,
    session_id: str,
    is_sandbox: bool,
) -> None:
    from apeiria.ai.acp.client import ACPClient

    client = ACPClient(agent_name, command, args, env)
    try:
        await client.connect()

        async def on_heartbeat(_tid: str, elapsed: float) -> None:
            await _inject_acp_message(
                session_id,
                f"[ACP] Task '{agent_name}' running... ({elapsed:.0f}s elapsed)",
            )

        result_text = await client.run_task(
            task_description,
            workspace=workspace,
            on_heartbeat=on_heartbeat,
        )

        await _inject_acp_message(
            session_id,
            f"[ACP] Task '{agent_name}' completed:\n{result_text}",
        )

    except TimeoutError:
        await _inject_acp_message(
            session_id,
            f"[ACP] Task '{agent_name}' timed out after 600s.",
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "ACP task failed for %s",
            agent_name,
            exc_info=True,
        )
        await _inject_acp_message(
            session_id,
            f"[ACP] Task '{agent_name}' failed.",
        )
    finally:
        await client.close()
        _active_tasks.pop(session_id, None)

        if is_sandbox:
            await asyncio.to_thread(_cleanup_sandbox, workspace)

        queue = _task_queue.get(session_id, [])
        if queue:
            queue.pop(0)
            if not queue:
                _task_queue.pop(session_id, None)
            logger.info(
                "Processing queued ACP task for session %s",
                session_id,
            )
