from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_core_settings_metadata_uses_advanced_disclosure() -> None:
    source = _read("web/src/views/CoreView.vue")

    assert "settings-list-row__advanced" in source
    assert '<details class="settings-list-row__advanced"' in source
    assert "settings-list-row__advanced-summary" in source
    assert "settings-list-row__value-summary" in source
    assert "core.showAdvancedDetails" in source
    assert "core.hideAdvancedDetails" in source
    assert "settings-list-row__advanced v-expansion-panels" not in source

    default_info_section = source.split('class="settings-list-row__control"', 1)[0]
    assert "settings-list-row__meta text-caption" not in default_info_section


def test_core_settings_visuals_match_workbench_focus_contract() -> None:
    source = _read("web/src/views/CoreView.vue")

    assert ".settings-list-row:focus-within" in source
    assert "box-shadow: inset 3px 0 0 rgba(var(--v-theme-primary)" in source
    assert "background: transparent;" in source
    assert "border: 0;" in source
    assert (
        ".settings-list-row__control :deep(.v-field--variant-outlined "
        ".v-field__outline)"
    ) in source
    assert "rgb(var(--v-theme-surface-container-low))" in source


def test_core_settings_editor_uses_compact_controls() -> None:
    source = _read("web/src/views/CoreView.vue")

    assert 'density="compact"' in source
    assert ".settings-list-row--compact" in source
    assert "padding: 10px 14px;" in source
    assert "min-height: 36px;" in source
    assert "row-gap: 8px;" in source


def test_adapter_management_default_view_is_overview_first() -> None:
    source = _read("web/src/views/core/AdapterManagementPanel.vue")

    default_view = source.split('<v-dialog v-model="adapterConfigDialogVisible"', 1)[0]

    assert "adapter-overview-strip" in default_view
    assert "adapter-status-list" in default_view
    assert "adapter-card" not in default_view
    assert "adapterOverviewAdvancedAction" in default_view
    assert "adapterOverviewRuntimeTitle" in source
    assert "adapterOverviewConfigTitle" in source
    assert "adapterOverviewRestartTitle" in source
    assert "adapterConfigDialogVisible" in source
    assert "adapterPreviewVisible" in source
    assert 'prepend-icon="mdi-package-variant-closed"' in default_view
    assert "core.adapterPreviewTitle" in source
    assert "core.adapterDiagnosticsAdvanced" in source
    assert "<v-text-field" not in default_view


def test_core_management_rows_have_subtle_interaction_polish() -> None:
    core_source = _read("web/src/views/CoreView.vue")
    adapter_source = _read("web/src/views/core/AdapterManagementPanel.vue")

    assert ".settings-list-row:hover" in core_source
    assert ".adapter-status-row:hover" in adapter_source
    assert "justify-self: end;" in adapter_source


def test_adapter_advanced_config_uses_shared_field_titles() -> None:
    source = _read("web/src/views/core/AdapterManagementPanel.vue")
    advanced_dialog = source.split(
        '<v-dialog v-model="adapterConfigDialogVisible"',
        1,
    )[1]

    assert "workbench-field__title" in source
    assert "workbench-field__helper" in source
    assert "workbench-field__control" in source
    assert ":aria-label=\"t('core.adapterModuleLabel')\"" in advanced_dialog
    assert ":label=\"t('core.adapterModuleLabel')\"" not in advanced_dialog


def test_adapter_management_composable_exposes_diagnostics() -> None:
    source = _read("web/src/views/core/useAdapterManagement.ts")

    for expected in (
        "blankRowCount",
        "duplicateModules",
        "addedModules",
        "removedModules",
        "unchangedModules",
        "previewItems",
        "normalizationNotes",
    ):
        assert expected in source


def test_core_locale_pairs_include_progressive_disclosure_copy() -> None:
    english = _read("web/src/locales/en_US.ts")
    chinese = _read("web/src/locales/zh_CN.ts")

    for key in (
        "showAdvancedDetails",
        "hideAdvancedDetails",
        "adapterOverviewAdvancedAction",
        "adapterOverviewEmptyAction",
        "adapterDiagnosticsSummary",
        "adapterDiagnosticsAdvanced",
        "adapterPreviewTitle",
        "adapterEmptyAction",
    ):
        assert key in english
        assert key in chinese


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
