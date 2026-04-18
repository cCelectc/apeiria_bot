"""Plugin configuration read/write services for Web UI and CLI adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from apeiria.app.governance import audit_service
from apeiria.app.plugins.registration_service import (
    AdapterConfigState,
    DriverConfigState,
    PluginConfigState,
    plugin_registration_config_service,
)
from apeiria.app.plugins.settings_support import (
    build_core_declared_configs,
    get_plugin_declared_configs,
    validate_and_coerce_updates,
)
from apeiria.app.plugins.settings_view import (
    build_core_setting_fields,
    build_plugin_setting_fields,
)
from apeiria.infra.config import (
    InvalidProjectConfigError,
    project_config_service,
)
from apeiria.infra.plugin_metadata.registry import PluginConfigConflictError

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.app.plugins.settings_support import PluginDeclaredConfig
    from apeiria.shared.plugin_metadata import RegisterConfig


class PluginSettingsNotConfigurableError(ValueError):
    """Raised when a plugin exists but exposes no editable config model."""


@dataclass(frozen=True)
class ConfigFieldView:
    key: str
    label: str
    type: str
    editor: str
    item_type: str | None
    key_type: str | None
    schema: object | None
    default: object | None
    help: str
    choices: list[dict[str, object]]
    base_value: object | None
    current_value: object | None
    local_value: object | None
    value_source: str
    global_key: str | None
    has_local_override: bool
    allows_null: bool
    editable: bool
    type_category: str
    order: int
    secret: bool


@dataclass(frozen=True)
class ConfigView:
    module_name: str
    section: str
    legacy_flatten: bool
    config_source: str
    has_config_model: bool
    fields: list[ConfigFieldView]


@dataclass(frozen=True)
class ConfigTextView:
    module_name: str
    section: str
    text: str


@dataclass(frozen=True)
class ConfigValidationReport:
    valid: bool
    message: str | None = None
    line: int | None = None
    column: int | None = None


ConfigMutationKind = Literal[
    "structured_patch",
    "raw_replace",
    "raw_validate",
]


@dataclass(frozen=True)
class ConfigMutation:
    module_name: str
    section: str
    mutation_kind: ConfigMutationKind
    values: dict[str, object | None] = field(default_factory=dict)
    clear: list[str] = field(default_factory=list)
    text: str | None = None


class _ConfigGovernanceFacade:
    """Build domain-level config views for Web UI and other adapters.

    This service centralizes:
    - current plugin/adapter/driver registration state
    - editable field metadata for config UIs
    - normalized write paths back into project TOML files
    """

    _CORE_SETTINGS_MODULE_NAME = "apeiria.core"

    def get_adapter_config(self) -> AdapterConfigState:
        return plugin_registration_config_service.get_adapter_config()

    def update_adapter_config(self, modules: list[str]) -> AdapterConfigState:
        return plugin_registration_config_service.update_adapter_config(modules)

    def get_driver_config(self) -> DriverConfigState:
        return plugin_registration_config_service.get_driver_config()

    def update_driver_config(self, builtin: list[str]) -> DriverConfigState:
        return plugin_registration_config_service.update_driver_config(builtin)

    def get_plugin_config(self) -> PluginConfigState:
        return plugin_registration_config_service.get_plugin_config()

    def update_plugin_config(
        self,
        modules: list[str],
        dirs: list[str],
    ) -> PluginConfigState:
        return plugin_registration_config_service.update_plugin_config(modules, dirs)

    def get_core_config_view(self) -> ConfigView:
        """Return editable NoneBot core settings with source metadata."""
        return ConfigView(
            module_name=self._CORE_SETTINGS_MODULE_NAME,
            section="nonebot",
            legacy_flatten=False,
            config_source="built_in",
            has_config_model=True,
            fields=build_core_setting_fields(),
        )

    def get_core_config_text(self) -> ConfigTextView:
        return ConfigTextView(
            module_name=self._CORE_SETTINGS_MODULE_NAME,
            section="nonebot",
            text=project_config_service.read_project_nonebot_section_toml(),
        )

    def update_core_config_view(
        self,
        values: dict[str, object | None],
        clear: list[str],
    ) -> ConfigView:
        mutation = ConfigMutation(
            module_name=self._CORE_SETTINGS_MODULE_NAME,
            section="nonebot",
            mutation_kind="structured_patch",
            values=dict(values),
            clear=list(clear),
        )
        result = self.apply_mutation(mutation)
        assert isinstance(result, ConfigView)
        return result

    def update_core_config_text(self, text: str) -> ConfigTextView:
        mutation = ConfigMutation(
            module_name=self._CORE_SETTINGS_MODULE_NAME,
            section="nonebot",
            mutation_kind="raw_replace",
            text=text,
        )
        result = self.apply_mutation(mutation)
        assert isinstance(result, ConfigTextView)
        return result

    def validate_core_config_text(self, text: str) -> ConfigValidationReport:
        return self.validate_mutation(
            ConfigMutation(
                module_name=self._CORE_SETTINGS_MODULE_NAME,
                section="nonebot",
                mutation_kind="raw_validate",
                text=text,
            )
        )

    def get_plugin_config_view(self, module_name: str) -> ConfigView:
        """Return editable settings for one plugin module."""
        declared = get_plugin_declared_configs(module_name)
        return ConfigView(
            module_name=module_name,
            section=declared.section,
            legacy_flatten=declared.legacy_flatten,
            config_source=declared.config_source,
            has_config_model=declared.has_config_model,
            fields=build_plugin_setting_fields(declared),
        )

    def get_plugin_config_text(self, module_name: str) -> ConfigTextView:
        declared = get_plugin_declared_configs(module_name)
        return ConfigTextView(
            module_name=module_name,
            section=declared.section,
            text=project_config_service.read_project_plugin_section_toml(
                declared.section
            ),
        )

    def update_plugin_config_view(
        self,
        module_name: str,
        values: dict[str, object | None],
        clear: list[str],
    ) -> ConfigView:
        """Validate and persist structured plugin setting updates."""
        declared = get_plugin_declared_configs(module_name)
        result = self.apply_mutation(
            ConfigMutation(
                module_name=module_name,
                section=declared.section,
                mutation_kind="structured_patch",
                values=dict(values),
                clear=list(clear),
            )
        )
        assert isinstance(result, ConfigView)
        return result

    def update_plugin_config_text(
        self,
        module_name: str,
        text: str,
    ) -> ConfigTextView:
        """Persist raw TOML for a single plugin config section."""
        declared = get_plugin_declared_configs(module_name)
        result = self.apply_mutation(
            ConfigMutation(
                module_name=module_name,
                section=declared.section,
                mutation_kind="raw_replace",
                text=text,
            )
        )
        assert isinstance(result, ConfigTextView)
        return result

    def validate_plugin_config_text(
        self,
        module_name: str,
        text: str,
    ) -> ConfigValidationReport:
        declared = get_plugin_declared_configs(module_name)
        return self.validate_mutation(
            ConfigMutation(
                module_name=module_name,
                section=declared.section,
                mutation_kind="raw_validate",
                text=text,
            )
        )

    def apply_mutation(self, mutation: ConfigMutation) -> ConfigView | ConfigTextView:
        if mutation.mutation_kind == "structured_patch":
            result = self._apply_structured_mutation(mutation)
        elif mutation.mutation_kind == "raw_replace":
            result = self._apply_raw_replace_mutation(mutation)
        else:
            msg = f"unsupported mutation kind for apply: {mutation.mutation_kind}"
            raise ValueError(msg)
        self._record_mutation_audit(mutation)
        return result

    def validate_mutation(self, mutation: ConfigMutation) -> ConfigValidationReport:
        if mutation.mutation_kind != "raw_validate":
            msg = f"unsupported mutation kind for validate: {mutation.mutation_kind}"
            raise ValueError(msg)
        return self._apply_raw_validate_mutation(mutation)

    @staticmethod
    def _record_mutation_audit(mutation: ConfigMutation) -> None:
        audit_service.record(
            "config.update",
            target_kind="config_namespace",
            target_id=mutation.module_name,
            detail=mutation.mutation_kind,
            metadata={
                "section": mutation.section,
                "changed_keys": sorted(mutation.values.keys()),
                "cleared_keys": list(mutation.clear),
            },
        )

    def _apply_structured_mutation(self, mutation: ConfigMutation) -> ConfigView:
        if mutation.module_name == self._CORE_SETTINGS_MODULE_NAME:
            configs = build_core_declared_configs()
            updates = validate_and_coerce_updates(
                mutation.values,
                mutation.clear,
                configs,
            )
            project_config_service.write_project_nonebot_config(updates)
            return self.get_core_config_view()

        declared = get_plugin_declared_configs(mutation.module_name)
        if not declared.has_config_model:
            raise PluginSettingsNotConfigurableError(mutation.module_name)
        updates = validate_and_coerce_updates(
            mutation.values,
            mutation.clear,
            declared.configs,
        )
        project_config_service.write_project_plugin_section_config(
            declared.section,
            updates,
            module_name=mutation.module_name,
        )
        return self.get_plugin_config_view(mutation.module_name)

    def _apply_raw_replace_mutation(self, mutation: ConfigMutation) -> ConfigTextView:
        if mutation.text is None:
            msg = "raw_replace mutation requires text"
            raise ValueError(msg)
        if mutation.module_name == self._CORE_SETTINGS_MODULE_NAME:
            project_config_service.write_project_nonebot_section_toml(mutation.text)
            return self.get_core_config_text()

        project_config_service.write_project_plugin_section_toml(
            mutation.section,
            mutation.text,
            module_name=mutation.module_name,
        )
        return self.get_plugin_config_text(mutation.module_name)

    def _apply_raw_validate_mutation(
        self,
        mutation: ConfigMutation,
    ) -> ConfigValidationReport:
        if mutation.text is None:
            msg = "raw_validate mutation requires text"
            raise ValueError(msg)
        text = mutation.text
        if mutation.module_name == self._CORE_SETTINGS_MODULE_NAME:
            return self._validate_raw_toml(
                lambda: project_config_service.validate_project_nonebot_section_toml(
                    text
                )
            )

        return self._validate_raw_toml(
            lambda: project_config_service.validate_project_plugin_section_toml(
                mutation.section,
                text,
            )
        )

    def _validate_raw_toml(
        self,
        validator: Callable[[], None],
    ) -> ConfigValidationReport:
        try:
            validator()
        except (TypeError, ValueError) as exc:
            return ConfigValidationReport(
                valid=False,
                message=str(exc) or exc.__class__.__name__,
                line=self._extract_error_position(exc, "line"),
                column=self._extract_error_position(exc, "col"),
            )
        return ConfigValidationReport(valid=True)

    def _extract_error_position(self, exc: Exception, attr: str) -> int | None:
        value = getattr(exc, attr, None)
        return value if isinstance(value, int) and value > 0 else None


class ConfigSchemaService:
    """Expose declared config schema and namespace metadata."""

    def get_core_declared_configs(self) -> list["RegisterConfig"]:
        return build_core_declared_configs()

    def get_plugin_declared_config(self, module_name: str) -> "PluginDeclaredConfig":
        return get_plugin_declared_configs(module_name)


class ConfigQueryService:
    """Read config governance views without exposing mutation methods."""

    def __init__(self, impl: _ConfigGovernanceFacade) -> None:
        self._impl = impl

    def get_core_view(self) -> ConfigView:
        return self._impl.get_core_config_view()

    def get_core_text(self) -> ConfigTextView:
        return self._impl.get_core_config_text()

    def get_adapter_config(self) -> AdapterConfigState:
        return self._impl.get_adapter_config()

    def get_driver_config(self) -> DriverConfigState:
        return self._impl.get_driver_config()

    def get_plugin_config(self) -> PluginConfigState:
        return self._impl.get_plugin_config()

    def get_plugin_view(self, module_name: str) -> ConfigView:
        return self._impl.get_plugin_config_view(module_name)

    def get_plugin_text(self, module_name: str) -> ConfigTextView:
        return self._impl.get_plugin_config_text(module_name)


class ConfigMutationService:
    """Apply and validate config mutations."""

    def __init__(self, impl: _ConfigGovernanceFacade) -> None:
        self._impl = impl

    def update_core_view(
        self,
        values: dict[str, object | None],
        clear: list[str],
    ) -> ConfigView:
        return self._impl.update_core_config_view(values, clear)

    def update_adapter_config(self, modules: list[str]) -> AdapterConfigState:
        return self._impl.update_adapter_config(modules)

    def update_driver_config(self, builtin: list[str]) -> DriverConfigState:
        return self._impl.update_driver_config(builtin)

    def update_plugin_config(
        self,
        modules: list[str],
        dirs: list[str],
    ) -> PluginConfigState:
        return self._impl.update_plugin_config(modules, dirs)

    def update_core_text(self, text: str) -> ConfigTextView:
        return self._impl.update_core_config_text(text)

    def validate_core_text(self, text: str) -> ConfigValidationReport:
        return self._impl.validate_core_config_text(text)

    def update_plugin_view(
        self,
        module_name: str,
        values: dict[str, object | None],
        clear: list[str],
    ) -> ConfigView:
        return self._impl.update_plugin_config_view(module_name, values, clear)

    def update_plugin_text(
        self,
        module_name: str,
        text: str,
    ) -> ConfigTextView:
        return self._impl.update_plugin_config_text(module_name, text)

    def validate_plugin_text(
        self,
        module_name: str,
        text: str,
    ) -> ConfigValidationReport:
        return self._impl.validate_plugin_config_text(module_name, text)

    def apply_mutation(self, mutation: ConfigMutation) -> ConfigView | ConfigTextView:
        return self._impl.apply_mutation(mutation)

    def validate_mutation(self, mutation: ConfigMutation) -> ConfigValidationReport:
        return self._impl.validate_mutation(mutation)


_config_governance_facade = _ConfigGovernanceFacade()
config_schema_service = ConfigSchemaService()
config_query_service = ConfigQueryService(_config_governance_facade)
config_mutation_service = ConfigMutationService(_config_governance_facade)

__all__ = [
    "AdapterConfigState",
    "ConfigFieldView",
    "ConfigMutation",
    "ConfigMutationKind",
    "ConfigMutationService",
    "ConfigQueryService",
    "ConfigSchemaService",
    "ConfigTextView",
    "ConfigValidationReport",
    "ConfigView",
    "DriverConfigState",
    "InvalidProjectConfigError",
    "PluginConfigConflictError",
    "PluginConfigState",
    "PluginSettingsNotConfigurableError",
    "config_mutation_service",
    "config_query_service",
    "config_schema_service",
]
