from __future__ import annotations

import json
from typing import Any

from nonebot.log import logger

from apeiria.ai.mcp.client import MCPClient
from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult

_active_clients: list[MCPClient] = []


async def connect_all() -> int:
    from sqlalchemy import select

    from apeiria.db.engine import get_session
    from apeiria.db.models.infrastructure import MCPServer

    async with get_session() as db:
        servers = list(
            (await db.execute(select(MCPServer).where(MCPServer.enabled == 1)))
            .scalars()
            .all()
        )

    registered = 0
    for server in servers:
        try:
            client = MCPClient(name=server.name, transport=server.transport)

            if server.transport == "stdio":
                args = json.loads(server.args_json) if server.args_json else []
                env = json.loads(server.env_json) if server.env_json else None
                await client.connect_stdio(server.command or "", args, env)
            elif server.transport == "sse":
                headers = (
                    json.loads(server.headers_json) if server.headers_json else None
                )
                await client.connect_sse(server.url or "", headers)

            tools_response = await client.request("tools/list")
            if isinstance(tools_response, list):
                tools_list = tools_response
            elif isinstance(tools_response, dict):
                tools_list = tools_response.get("tools", [])
            else:
                tools_list = []

            for tool_def in tools_list:
                if not isinstance(tool_def, dict):
                    continue
                name = tool_def.get("name", "")
                if not name:
                    continue

                mcp_tool = _wrap_mcp_tool(client, name, tool_def)
                register_tool(mcp_tool)
                registered += 1

            _active_clients.append(client)
            logger.info(
                "MCP server '%s': %d tools registered",
                server.name,
                len(tools_list),
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to connect MCP server '%s'",
                server.name,
                exc_info=True,
            )

    return registered


def _wrap_mcp_tool(
    client: MCPClient,
    name: str,
    tool_def: dict[str, Any],
) -> Tool:
    async def execute(**kwargs: Any) -> ToolResult:
        if not client.connected:
            return ToolResult(success=False, error="MCP server disconnected")
        try:
            result = await client.request(
                "tools/call",
                {"name": name, "arguments": kwargs},
            )
            content = (
                result
                if isinstance(result, str)
                else json.dumps(result)
                if result
                else ""
            )
            return ToolResult(success=True, content=content)
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=str(e))

    return Tool(
        name=name,
        description=tool_def.get("description", ""),
        parameters=tool_def.get(
            "inputSchema",
            tool_def.get(
                "parameters",
                {"type": "object", "properties": {}},
            ),
        ),
        execute=execute,
    )


async def close_all() -> None:
    for client in _active_clients:
        try:
            await client.close()
        except Exception:  # noqa: BLE001, PERF203
            logger.warning(
                "Error closing MCP client %s",
                client.name,
                exc_info=True,
            )
    _active_clients.clear()
