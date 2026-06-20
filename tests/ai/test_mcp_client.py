from __future__ import annotations


def test_mcp_tool_wrapping() -> None:
    from apeiria.ai.mcp.client import MCPClient
    from apeiria.ai.mcp.registry import _wrap_mcp_tool

    client = MCPClient("test", "stdio")
    tool_def = {
        "name": "test_tool",
        "description": "A test",
        "inputSchema": {
            "type": "object",
            "properties": {"x": {"type": "string"}},
        },
    }
    tool = _wrap_mcp_tool(client, "test_tool", tool_def)
    assert tool.name == "test_tool"
    assert tool.description == "A test"
    assert tool.parameters["properties"]["x"]["type"] == "string"


def test_mcp_tool_default_schema() -> None:
    from apeiria.ai.mcp.client import MCPClient
    from apeiria.ai.mcp.registry import _wrap_mcp_tool

    client = MCPClient("test", "stdio")
    tool_def = {"name": "bare_tool", "description": "No schema"}
    tool = _wrap_mcp_tool(client, "bare_tool", tool_def)
    assert tool.name == "bare_tool"
    assert tool.parameters == {"type": "object", "properties": {}}
