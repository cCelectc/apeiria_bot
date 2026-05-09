from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ai_model_connection_uses_explicit_provider_detail_states() -> None:
    source_state = _read("web/src/composables/aiModels/sourceState.ts")
    tab_state = _read("web/src/composables/useAIModelsTab.ts")
    page = _read("web/src/views/ai/AIModelsPage.vue")

    assert "export type AIProviderDetailMode" in source_state
    assert "providerDetailMode = ref<AIProviderDetailMode>('empty')" in source_state
    assert "providerDetailMode.value = 'selected'" in source_state
    assert "providerDetailMode.value = 'creating'" in source_state
    assert "providerDetailMode.value = 'empty'" in source_state
    assert "clearSourceSelection" in source_state
    assert "sourceState.clearSourceSelection()" in tab_state

    no_sources_branch = tab_state.split(
        "if (sourceState.sources.value.length > 0)",
        1,
    )[1]
    assert "sourceState.startCreateSource()" not in no_sources_branch

    assert "providerDetailMode === 'empty'" in page
    assert "providerDetailMode !== 'empty'" in page
    assert "ai-provider-empty-state" in page
    assert "sourceProviderPickPrompt" in page
    assert "AISourceWorkspace" in page
    assert "AISourceModelsPanel" in page


def test_ai_model_connection_uses_workbench_resource_primitives() -> None:
    page = _read("web/src/views/ai/AIModelsPage.vue")
    source_list = _read("web/src/views/ai/AISourceListPanel.vue")
    source_models = _read("web/src/views/ai/AISourceModelsPanel.vue")

    for component in (
        "SplitPane",
        "DetailPanel",
    ):
        assert component in page

    for component in (
        "SelectableList",
        "SelectableListItem",
        "EmptyState",
    ):
        assert component in source_list

    default_list = source_list.split("<v-menu", 1)[0]
    assert "<v-list" not in default_list
    assert "mdi-delete-outline" not in default_list
    assert "sourceProviderEmptyTitle" not in page
    assert "sourceProviderSelectTitle" not in page

    assert "EmptyState" in source_models
    assert "modelAdvancedDialog" in source_models
    assert "common.noData" not in source_models


def test_ai_source_protocol_selection_keeps_api_base_explicit() -> None:
    source_state = _read("web/src/composables/aiModels/sourceState.ts")
    source_workspace = _read("web/src/views/ai/AISourceWorkspace.vue")
    api_types = _read("web/src/api/ai/types.ts")

    assert "default_api_base" not in source_state
    assert "default_api_base" not in source_workspace
    assert "default_api_base" not in api_types
    protocol_handler = source_state.split(
        "function selectSourceProtocol",
        1,
    )[1].split("function clearSourceSelection", 1)[0]
    assert "sourceForm.api_base" not in protocol_handler


def test_ai_model_connection_locales_cover_empty_and_advanced_states() -> None:
    for path in ("web/src/locales/en_US.ts", "web/src/locales/zh_CN.ts"):
        source = _read(path)
        for key in (
            "sourceProviderEmptyTitle",
            "sourceProviderEmptyText",
            "sourceProviderSelectTitle",
            "sourceProviderSelectText",
            "sourceProviderPickPrompt",
            "sourceAdvancedConfigAction",
            "modelAdvancedConfigAction",
            "modelEmptyTitle",
            "modelEmptyText",
            "profileEmptyTitle",
            "profileEmptyText",
        ):
            assert key in source, f"{key} missing from {path}"


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
