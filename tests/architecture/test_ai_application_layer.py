from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ai_application_target_layout_exists() -> None:
    expected_paths = (
        "apeiria/app/ai/application.py",
        "apeiria/app/ai/runtime/__init__.py",
        "apeiria/app/ai/runtime/entry.py",
        "apeiria/app/ai/runtime/ingress/__init__.py",
        "apeiria/app/ai/runtime/session/__init__.py",
        "apeiria/app/ai/runtime/context/__init__.py",
        "apeiria/app/ai/runtime/planning/__init__.py",
        "apeiria/app/ai/runtime/execution/__init__.py",
        "apeiria/app/ai/runtime/commit/__init__.py",
        "apeiria/app/ai/runtime/trace/__init__.py",
        "apeiria/app/ai/sessions/__init__.py",
        "apeiria/app/ai/future_tasks/__init__.py",
        "apeiria/app/ai/operations/__init__.py",
        "apeiria/app/ai/diagnostics/__init__.py",
        "apeiria/app/ai/lifecycle.py",
    )

    missing = tuple(path for path in expected_paths if not (REPO_ROOT / path).exists())

    assert not missing


def test_ai_application_import_is_light() -> None:
    for module_name in (
        "apeiria.app.ai.application",
        "apeiria.app.ai.pipeline.service",
        "apeiria.ai.model.adapters.openai_compatible",
        "apeiria.ai.model.adapters.anthropic_compatible",
        "apeiria.webui.routes.ai",
        "apeiria.webui.routes.ai.models",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.application")

    assert module.__name__ == "apeiria.app.ai.application"
    assert "apeiria.app.ai.pipeline.service" not in sys.modules
    assert "apeiria.ai.model.adapters.openai_compatible" not in sys.modules
    assert "apeiria.ai.model.adapters.anthropic_compatible" not in sys.modules
    assert "apeiria.webui.routes.ai" not in sys.modules
    assert "apeiria.webui.routes.ai.models" not in sys.modules


def test_ai_application_composes_focused_entries() -> None:
    module = importlib.import_module("apeiria.app.ai.application")
    app = module.AIApplication()

    assert app.runtime is not None
    assert app.sessions is not None
    assert app.future_tasks is not None
    assert app.operations is not None
    assert app.diagnostics is not None
    assert app.lifecycle is not None


def test_ai_package_exports_application_boundary_only() -> None:
    module = importlib.import_module("apeiria.app.ai")

    assert module.__all__ == ["AIApplication", "ai_application"]
    assert module.AIApplication.__module__ == "apeiria.app.ai.application"
    assert module.ai_application.__class__ is module.AIApplication
    assert not hasattr(module, "ai_runtime_service")
    assert not hasattr(module, "AIRuntimeService")
    assert not hasattr(module, "AIRuntimeReplyRequest")
    assert not hasattr(module, "ReplyInputs")


def test_ai_application_constructor_accepts_replacement_entries() -> None:
    module = importlib.import_module("apeiria.app.ai.application")
    replacements = {
        "runtime": object(),
        "sessions": object(),
        "future_tasks": object(),
        "operations": object(),
        "diagnostics": object(),
        "lifecycle": object(),
    }

    app = module.AIApplication(**replacements)

    for name, replacement in replacements.items():
        assert getattr(app, name) is replacement


def test_ai_application_boundary_imports_do_not_bypass_entries() -> None:
    imports = _imports_for("apeiria/app/ai/application.py")

    forbidden = (
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.session_runtime",
        "apeiria.app.ai.session_read",
        "apeiria.app.ai.future_task",
        "apeiria.app.ai.admin",
        "apeiria.webui",
        "apeiria.ai.model.adapters",
    )

    violations = tuple(
        imported
        for imported in imports
        if any(
            imported == prefix or imported.startswith(prefix + ".")
            for prefix in forbidden
        )
    )

    assert not violations


def test_ai_application_object_stays_composition_only() -> None:
    path = REPO_ROOT / "apeiria/app/ai/application.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_calls = (
        "build_prompt",
        "select_model",
        "generate",
        "execute_tool",
        "execute_tool_intents",
        "persist_assistant_message",
        "store_trace",
        "create_task",
        "cancel_task",
        "update_relationship_state",
        "store_extracted_memories",
    )
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_default_"):
                continue
            if node.name not in {"startup", "inspect"}:
                violations.append(f"method {node.name}")
        if isinstance(node, ast.Call) and _call_name(node) in forbidden_calls:
            violations.append(f"calls {_call_name(node)}")

    assert not violations


def test_runtime_package_does_not_import_management_or_surface_layers() -> None:
    violations: list[str] = []
    forbidden = (
        "apeiria.app.ai.operations",
        "apeiria.app.ai.sessions",
        "apeiria.app.ai.diagnostics",
        "apeiria.app.ai.admin",
        "apeiria.app.ai.pipeline",
        "apeiria.webui",
    )
    for path in (REPO_ROOT / "apeiria/app/ai/runtime").rglob("*.py"):
        violations.extend(
            f"{path.relative_to(REPO_ROOT)} -> {imported}"
            for imported in _imports_for_path(path)
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden
            )
        )

    assert not violations


def test_builtin_ai_plugin_lifecycle_enters_application_boundary() -> None:
    imports = _imports_for("apeiria/builtin_plugins/ai.py")
    source = (REPO_ROOT / "apeiria/builtin_plugins/ai.py").read_text(encoding="utf-8")

    assert "apeiria.app.ai" in imports
    assert "apeiria.app.ai.lifecycle" not in imports
    assert "apeiria.app.ai.pipeline" not in imports
    assert "ai_application.lifecycle.startup" in source
    assert "ai_application.runtime.handle_message" in source


def test_webui_session_routes_enter_application_sessions() -> None:
    imports = _imports_for("apeiria/webui/routes/ai/sessions.py")
    source = (REPO_ROOT / "apeiria/webui/routes/ai/sessions.py").read_text(
        encoding="utf-8"
    )

    assert "apeiria.app.ai" in imports
    assert not any(
        imported == "apeiria.app.ai.session_read"
        or imported.startswith("apeiria.app.ai.session_read.")
        for imported in imports
    )
    assert "ai_application.sessions." in source


def test_webui_ai_routes_do_not_import_old_application_packages() -> None:
    violations: list[str] = []
    forbidden = (
        "apeiria.app.ai.admin",
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.session_read",
        "apeiria.app.ai.future_task",
    )
    for path in (REPO_ROOT / "apeiria/webui/routes/ai").glob("*.py"):
        violations.extend(
            f"{path.relative_to(REPO_ROOT)} -> {imported}"
            for imported in _imports_for_path(path)
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden
            )
        )

    assert not violations


def test_ai_code_and_public_tests_do_not_import_deleted_application_packages() -> None:
    forbidden = (
        "apeiria.app.ai.admin",
        "apeiria.app.ai.future_task",
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.session_read",
        "apeiria.app.ai.session_runtime",
    )
    scanned_roots = (
        REPO_ROOT / "apeiria",
        REPO_ROOT / "tests/ai",
    )
    violations: list[str] = []
    for root in scanned_roots:
        for path in root.rglob("*.py"):
            violations.extend(
                f"{path.relative_to(REPO_ROOT)} -> {imported}"
                for imported in _imports_for_path(path)
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in forbidden
                )
            )

    assert not violations


def test_ai_runtime_behavior_tests_use_current_boundary_names() -> None:
    stale_paths = tuple(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "tests/ai").glob("test_session_runtime_*.py")
    )

    assert not stale_paths


def test_prompt_preview_read_side_uses_role_precise_names() -> None:
    path = REPO_ROOT / "apeiria/app/ai/sessions/prompt_preview.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    vague_class_names = tuple(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and "Facade" in node.name
    )
    source = path.read_text(encoding="utf-8")

    assert not vague_class_names
    assert "read facade" not in source.lower()
    assert '"session_read"' not in source


def test_live_runtime_obtains_production_defaults_from_composition() -> None:
    composition_path = REPO_ROOT / "apeiria/app/ai/runtime/composition.py"
    live_path = REPO_ROOT / "apeiria/app/ai/runtime/live.py"
    live_imports = _imports_for_path(live_path)
    live_source = live_path.read_text(encoding="utf-8")
    composition_owned_names = (
        "RuntimeCommitEffectsStage",
        "AssistantReplyPersistenceStage",
        "RuntimeContextAssemblyStage",
        "RuntimeObservationEffectsStage",
        "RuntimePolicyDecisionStage",
        "RuntimeTraceProjectionStage",
        "RuntimeTurnExecutionStage",
        "RuntimeTurnPlanningStage",
        "deliver_generated_reply",
        "gather_reply_inputs",
        "turn_trace_repository",
    )

    assert composition_path.is_file()
    assert "apeiria.app.ai.runtime.composition" in live_imports
    assert "_default_session_runtime_resolver" not in live_source
    assert not any(name in live_source for name in composition_owned_names)


def test_turn_orchestrator_keeps_default_stage_classes_in_focused_modules() -> None:
    source = (REPO_ROOT / "apeiria/app/ai/runtime/orchestrator.py").read_text(
        encoding="utf-8"
    )
    default_stage_classes = (
        "class RuntimePolicyDecisionStage",
        "class RuntimeObservationEffectsStage",
        "class RuntimeContextAssemblyStage",
        "class RuntimeTurnPlanningStage",
        "class RuntimeTurnExecutionStage",
    )

    assert not any(name in source for name in default_stage_classes)


def test_operations_and_diagnostics_have_focused_domains() -> None:
    expected_operations = (
        "models.py",
        "sources.py",
        "personas.py",
        "memories.py",
        "relationships.py",
        "person_profiles.py",
        "tools.py",
        "future_tasks.py",
    )
    expected_diagnostics = (
        "traces.py",
        "readiness.py",
        "model_connectivity.py",
        "workbench.py",
        "audit.py",
        "debug.py",
        "prompt_preview.py",
    )

    assert not _missing_files("apeiria/app/ai/operations", expected_operations)
    assert not _missing_files("apeiria/app/ai/diagnostics", expected_diagnostics)


def test_diagnostics_modules_are_read_only_boundaries() -> None:
    forbidden_calls = (
        "create_task",
        "cancel_task",
        "mark_task_failed",
        "mark_task_sent",
        "execute_tool_intents",
        "persist_assistant_message",
        "persist_tool_observations",
        "send",
        "generate",
    )
    violations: list[str] = []
    for path in (REPO_ROOT / "apeiria/app/ai/diagnostics").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            f"{path.relative_to(REPO_ROOT)} calls {_call_name(node)}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node) in forbidden_calls
        )

    assert not violations


def test_runtime_planning_has_focused_sub_boundaries() -> None:
    expected_modules = (
        "reply_decision.py",
        "model_selection.py",
        "prompts.py",
        "skills.py",
        "tool_intents.py",
        "tool_exposure.py",
    )

    assert not _missing_files("apeiria/app/ai/runtime/planning", expected_modules)


def test_ai_capability_layer_does_not_import_application_layer() -> None:
    forbidden = (
        "apeiria.app.ai",
        "apeiria.webui.routes.ai",
        "apeiria.builtin_plugins.ai",
    )
    violations: list[str] = []
    for path in (REPO_ROOT / "apeiria/ai").rglob("*.py"):
        violations.extend(
            f"{path.relative_to(REPO_ROOT)} -> {imported}"
            for imported in _imports_for_path(path)
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden
            )
        )

    assert not violations


def test_ai_capability_contract_package_is_foundation_only() -> None:
    forbidden = (
        "apeiria.app.ai",
        "apeiria.webui",
        "apeiria.builtin_plugins",
        "apeiria.ai.model.adapters",
        "nonebot",
    )
    violations: list[str] = []
    for path in (REPO_ROOT / "apeiria/ai/capabilities").rglob("*.py"):
        violations.extend(
            f"{path.relative_to(REPO_ROOT)} -> {imported}"
            for imported in _imports_for_path(path)
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden
            )
        )

    assert not violations


def test_ai_capability_public_surfaces_exclude_application_orchestration() -> None:
    ai_module = importlib.import_module("apeiria.ai")
    model_module = importlib.import_module("apeiria.ai.model")
    tools_module = importlib.import_module("apeiria.ai.tools")

    assert not {
        "AIService",
        "AIServiceStatus",
        "ai_service",
        "model_gateway",
        "tool_gateway",
    } & set(ai_module.__all__)
    assert not {"AIModelFacade", "ai_model_facade"} & set(model_module.__all__)
    assert "ModelInvoker" in model_module.__all__
    assert "model_invoker" in model_module.__all__
    assert not {
        "ToolGateway",
        "ToolGatewayRequest",
        "ToolGatewayResult",
        "tool_gateway",
        "RuntimeToolLoopRunner",
        "runtime_tool_loop_runner",
    } & set(tools_module.__all__)


def test_auxiliary_capability_modules_do_not_select_or_invoke_models() -> None:
    forbidden_calls = ("select_model", "generate_text")
    checked_paths = (
        REPO_ROOT / "apeiria/ai/skills",
        REPO_ROOT / "apeiria/ai/tools",
        REPO_ROOT / "apeiria/ai/prompting",
    )
    violations: list[str] = []
    for root in checked_paths:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            violations.extend(
                f"{path.relative_to(REPO_ROOT)} calls {_call_name(node)}"
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and _call_name(node) in forbidden_calls
            )

    assert not violations


def test_runtime_execution_owns_model_tool_loop_runner() -> None:
    tools_source = (REPO_ROOT / "apeiria/ai/tools/__init__.py").read_text(
        encoding="utf-8"
    )
    execution_source = (
        REPO_ROOT / "apeiria/app/ai/runtime/execution/tool_loop.py"
    ).read_text(encoding="utf-8")
    runtime_imports = _imports_for_path(
        REPO_ROOT / "apeiria/app/ai/runtime/execution/__init__.py"
    )

    assert "class RuntimeToolLoopRunner" in execution_source
    assert "runtime_tool_loop_runner" in execution_source
    assert "ToolGateway" not in tools_source
    assert "apeiria.ai.tools.gateway" not in runtime_imports


def test_builtin_ai_status_uses_application_diagnostics() -> None:
    imports = _imports_for("apeiria/builtin_plugins/ai.py")
    source = (REPO_ROOT / "apeiria/builtin_plugins/ai.py").read_text(encoding="utf-8")

    assert "apeiria.app.ai" in imports
    assert "from apeiria.ai import ai_service" not in source
    assert "ai_application.diagnostics.get_runtime_status" in source


def _missing_files(directory: str, filenames: tuple[str, ...]) -> tuple[str, ...]:
    base = REPO_ROOT / directory
    return tuple(filename for filename in filenames if not (base / filename).is_file())


def _imports_for(relative_path: str) -> tuple[str, ...]:
    return _imports_for_path(REPO_ROOT / relative_path)


def _imports_for_path(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(_resolve_import(path, node))
    return tuple(imports)


def _resolve_import(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        assert node.module is not None
        return node.module

    package_parts = list(path.relative_to(REPO_ROOT).with_suffix("").parts[:-1])
    target_parts = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        target_parts.extend(node.module.split("."))
    return ".".join(target_parts)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None
