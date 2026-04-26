from __future__ import annotations

from apeiria.runtime import (
    ApeiriaPackageBand,
    classify_package,
    iter_package_rules,
    planned_app_target,
)
from apeiria.runtime.package_map import (
    APP_PREFIXES,
    INFRASTRUCTURE_PREFIXES,
    STABLE_ROOT_BOUNDARY_EXCLUSIONS,
    STABLE_ROOT_PREFIXES,
    SURFACE_PREFIXES,
)


def test_runtime_package_map_classifies_current_ownership_bands() -> None:
    conversation_rule = classify_package("apeiria.conversation.service")
    app_rule = classify_package("apeiria.app.ai.pipeline")
    surface_rule = classify_package("apeiria.webui.routes.chat")
    runtime_rule = classify_package("apeiria.runtime.context")

    assert conversation_rule is not None
    assert conversation_rule.band == ApeiriaPackageBand.STABLE_ROOT
    assert app_rule is not None
    assert app_rule.band == ApeiriaPackageBand.APP
    assert surface_rule is not None
    assert surface_rule.band == ApeiriaPackageBand.SURFACE
    assert runtime_rule is not None
    assert runtime_rule.band == ApeiriaPackageBand.INFRASTRUCTURE
    assert classify_package("apeiria.unknown.module") is None


def test_runtime_package_map_exposes_boundary_prefix_sets() -> None:
    assert "apeiria.runtime" in INFRASTRUCTURE_PREFIXES
    assert "apeiria.conversation" in STABLE_ROOT_PREFIXES
    assert "apeiria.app" in APP_PREFIXES
    assert "apeiria.webui" in SURFACE_PREFIXES
    assert STABLE_ROOT_BOUNDARY_EXCLUSIONS == (
        "apeiria.access.webui_auth",
        "apeiria.plugins.store",
    )


def test_runtime_package_map_tracks_planned_app_moves() -> None:
    assert planned_app_target("apeiria.ai.pipeline.service") == (
        "apeiria.app.ai.pipeline.service"
    )
    assert planned_app_target("apeiria.ai.conversation.summary") == (
        "apeiria.app.ai.conversation_context.summary"
    )
    assert planned_app_target("apeiria.plugins.store.service") == (
        "apeiria.app.plugins.store.service"
    )
    assert planned_app_target("apeiria.access.webui_auth.service") == (
        "apeiria.app.access.webui_auth.service"
    )
    assert planned_app_target("apeiria.conversation.service") is None


def test_runtime_package_map_rules_include_new_app_band() -> None:
    rules = iter_package_rules()

    assert any(
        rule.prefix == "apeiria.app" and rule.band == ApeiriaPackageBand.APP
        for rule in rules
    )
