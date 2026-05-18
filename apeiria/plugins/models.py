"""Shared plugin application models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PluginDescriptor:
    """Contract-facing plugin identity and declaration fields."""

    module_name: str
    name: str
    description: str | None
    homepage: str | None
    source: str
    plugin_type: str
    author: str | None = None
    version: str | None = None
    is_ui_hidden: bool = False


@dataclass(frozen=True)
class HandlerDescriptor:
    """Minimal handler contract projected from one native matcher."""

    handler_id: str
    plugin_module: str
    phase: str
    subject_kind: str
    priority: int
    propagation_mode: str
    matcher_type: str
    is_temporary: bool = False


@dataclass(frozen=True)
class PluginRuntimeState:
    """Runtime-facing plugin facts observed by the host."""

    is_loaded: bool
    is_pending_uninstall: bool = False


@dataclass(frozen=True)
class PluginGovernanceState:
    """Governance-facing plugin state exposed to management surfaces."""

    kind: str = "plugin"
    access_mode: str = "default_allow"
    is_global_enabled: bool = True
    is_protected: bool = False
    protected_reason: str | None = None
    is_explicit: bool = False
    is_dependency: bool = False
    can_edit_config: bool = True
    can_view_readme: bool = False
    can_enable_disable: bool = False
    can_uninstall: bool = False
    required_plugins: list[str] = field(default_factory=list)
    dependent_plugins: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginPackageBinding:
    """Operations-facing package binding facts for one plugin."""

    installed_package: str | None = None
    installed_module_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginCatalogEntry:
    """Composite catalog entry built from contract, runtime, and governance facts."""

    descriptor: PluginDescriptor
    runtime_state: PluginRuntimeState
    governance_state: PluginGovernanceState
    handler_descriptors: list[HandlerDescriptor] = field(default_factory=list)
    package_binding: PluginPackageBinding = field(default_factory=PluginPackageBinding)
    child_plugin_modules: list[str] = field(default_factory=list)
    ui_order: int = 99


@dataclass(frozen=True)
class PluginUninstallResult:
    """Result of one plugin uninstall operation."""

    requirement: str
    module_names: list[str]
