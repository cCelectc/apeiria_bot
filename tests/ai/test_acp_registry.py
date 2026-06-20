from __future__ import annotations


def test_acp_tool_name_format() -> None:
    from apeiria.ai.acp.registry import _build_acp_tool

    tool = _build_acp_tool("myagent", "python", ["-m", "agent"], None, None)
    assert tool.name == "acp_myagent"
    assert "task" in tool.parameters["properties"]
    assert tool.parameters["required"] == ["task"]


def test_acp_tool_description_contains_agent_name() -> None:
    from apeiria.ai.acp.registry import _build_acp_tool

    tool = _build_acp_tool("coder", "node", ["index.js"], None, None)
    assert "coder" in tool.description
