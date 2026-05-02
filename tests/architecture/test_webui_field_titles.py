from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_shared_field_title_classes_exist() -> None:
    app_css = (REPO_ROOT / "web" / "src" / "styles" / "app.css").read_text(
        encoding="utf-8",
    )

    assert ".workbench-field" in app_css
    assert ".workbench-field__title" in app_css
    assert ".workbench-field__helper" in app_css
    assert ".workbench-field-row" in app_css


def test_ai_source_workspace_uses_shared_field_titles() -> None:
    source = _read_vue("web/src/views/ai/AISourceWorkspace.vue")

    assert "source-config-row__label" not in source
    assert "source-config-row__hint" not in source
    for label_key in (
        "ai.sourceAdapterKind",
        "ai.capabilityMetadata",
        "ai.defaultOptions",
        "ai.capabilityProvenance",
        "ai.sourceEnabled",
    ):
        assert f":label=\"t('{label_key}')\"" not in source
        assert f"t('{label_key}')" in source


def test_ai_model_and_persona_forms_use_shared_field_titles() -> None:
    source_model = _read_vue("web/src/views/ai/AISourceModelsPanel.vue")
    personas = _read_vue("web/src/views/ai/AIPersonasPanel.vue")

    for label_key in (
        "ai.modelIdentifier",
        "ai.modelDisplayName",
        "ai.modelEnabled",
        "ai.modelProfileName",
        "ai.modelProfileEnabled",
    ):
        assert f":label=\"t('{label_key}')\"" not in source_model
        assert f"t('{label_key}')" in source_model

    for label_key in (
        "ai.personaName",
        "ai.personaSystemPrompt",
        "ai.personaEnabled",
    ):
        assert f":label=\"t('{label_key}')\"" not in personas
        assert f"t('{label_key}')" in personas


def test_plugin_structured_editor_uses_shared_field_titles() -> None:
    source = _read_vue("web/src/views/plugins/SettingsStructuredEditor.vue")

    assert "structured-object__label" not in source
    assert "structured-object__help" not in source
    assert "workbench-field__title" in source
    assert "workbench-field__helper" in source
    assert "workbench-field-row" in source


def test_auth_forms_use_shared_field_titles() -> None:
    for path, label_keys in {
        "web/src/views/LoginView.vue": ("login.username", "login.password"),
        "web/src/views/RegisterView.vue": (
            "register.registrationCode",
            "register.username",
            "register.password",
            "register.confirmPassword",
        ),
    }.items():
        source = _read_vue(path)
        assert "auth-form" in source
        for label_key in label_keys:
            assert f":label=\"t('{label_key}')\"" not in source
            assert f"t('{label_key}')" in source


def test_authenticated_migrated_forms_keep_responsive_field_groups() -> None:
    for path in (
        "web/src/views/AccountsView.vue",
        "web/src/views/LogHistoryView.vue",
        "web/src/views/LogsView.vue",
        "web/src/views/PermissionsView.vue",
        "web/src/views/ai/AIDebugPanel.vue",
        "web/src/views/ai/AIMemoriesPanel.vue",
        "web/src/views/ai/AIPersonProfilesPanel.vue",
    ):
        source = _read_vue(path)

        assert "workbench-field__title" in source, path
        assert "workbench-field__control" in source, path
        assert ':aria-label="t(' in source, path
        assert ':label="t(' not in source, path


def _read_vue(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
