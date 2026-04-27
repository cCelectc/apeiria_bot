from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ai_tools_routes_do_not_keep_debug_skill_aliases() -> None:
    routes_source = (
        REPO_ROOT / "apeiria" / "webui" / "routes" / "ai" / "tools.py"
    ).read_text(encoding="utf-8")

    assert "/debug/skills" not in routes_source
    assert "boundary-freeze phase" not in routes_source


def test_browser_ai_tools_api_uses_canonical_tool_routes() -> None:
    api_source = (REPO_ROOT / "web" / "src" / "api" / "ai" / "tools.ts").read_text(
        encoding="utf-8"
    )
    debug_tools_source = (
        REPO_ROOT / "web" / "src" / "composables" / "useAIDebugToolsTab.ts"
    ).read_text(encoding="utf-8")

    assert "/ai/debug/skills" not in api_source
    assert "previewAISkillPolicyDebug" not in api_source
    assert "previewAISkillCapabilityDebug" not in api_source
    assert "previewAISkillPolicyDebug" not in debug_tools_source
    assert "previewAISkillCapabilityDebug" not in debug_tools_source
