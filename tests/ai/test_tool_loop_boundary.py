from __future__ import annotations

import ast
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "apeiria" / "ai" / "tools"
LOOP_ROOT = TOOLS_ROOT / "loop"
GATEWAY_MODULE = TOOLS_ROOT / "gateway.py"
LOOP_MODULES = (
    LOOP_ROOT / "__init__.py",
    LOOP_ROOT / "history.py",
    LOOP_ROOT / "projection.py",
    LOOP_ROOT / "prompt_budget.py",
    LOOP_ROOT / "state.py",
)
PUBLIC_GATEWAY_EXPORTS = (
    "ToolGateway",
    "ToolGatewayRequest",
    "ToolGatewayResult",
    "ToolResult",
    "tool_gateway",
)
FORBIDDEN_GATEWAY_HELPERS = (
    "_repair_tool_message_history",
    "_recover_prompt_budget_messages",
    "_is_context_pressure_error",
    "_project_tool_results",
    "_completed_observations",
    "_summarize_arguments",
)


def test_ai_tool_loop_internal_modules_exist() -> None:
    missing = tuple(
        str(path.relative_to(REPO_ROOT)) for path in LOOP_MODULES if not path.is_file()
    )
    assert not missing


def test_ai_tool_loop_public_gateway_exports_remain_stable() -> None:
    package = importlib.import_module("apeiria.ai.tools")
    gateway = importlib.import_module("apeiria.ai.tools.gateway")

    for name in PUBLIC_GATEWAY_EXPORTS:
        assert name in package.__all__
        assert getattr(package, name) is getattr(gateway, name)


def test_gateway_does_not_reintroduce_loop_helper_implementations() -> None:
    tree = ast.parse(GATEWAY_MODULE.read_text(encoding="utf-8"))
    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    violations = sorted(function_names.intersection(FORBIDDEN_GATEWAY_HELPERS))
    assert not violations


def test_tool_loop_helpers_do_not_import_pipeline_modules() -> None:
    violations: list[str] = []
    for path in LOOP_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("apeiria.app.ai.pipeline"):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{module}")
            elif isinstance(node, ast.Import):
                violations.extend(
                    f"{path.relative_to(REPO_ROOT)}:{alias.name}"
                    for alias in node.names
                    if alias.name.startswith("apeiria.app.ai.pipeline")
                )

    assert not violations
