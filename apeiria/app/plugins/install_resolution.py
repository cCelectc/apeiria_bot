"""Plugin installation source resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from apeiria.app.plugins.store.workflows import (
    PackageStoreItemRequest,
    package_store_workflow,
)
from apeiria.config.plugins import plugin_config_service
from apeiria.plugins.install import resolve_plugin_module_candidates_from_requirement
from apeiria.utils.project_context import current_project_root

InstallSourceKind = Literal["store_item", "requirement", "local_path"]
InstallResolutionStatus = Literal[
    "resolved",
    "ambiguous",
    "unresolved",
    "invalid",
    "installed",
]
InstallActionKind = Literal[
    "install_package",
    "register_local_module",
    "register_local_directory",
]


@dataclass(frozen=True, slots=True)
class PluginInstallSource:
    kind: InstallSourceKind
    value: str | None = None
    source_id: str | None = None
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class PluginInstallCandidate:
    module_name: str
    kind: Literal["module", "directory"] = "module"
    confidence: Literal["high", "medium", "low"] = "medium"
    reason: str = ""
    already_registered: bool = False
    already_loaded: bool = False


@dataclass(frozen=True, slots=True)
class PluginInstallAction:
    kind: InstallActionKind
    requirement: str | None = None
    module_name: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class PluginInstallResolution:
    source: PluginInstallSource
    status: InstallResolutionStatus
    candidates: list[PluginInstallCandidate] = field(default_factory=list)
    default_action: PluginInstallAction | None = None
    warnings: list[str] = field(default_factory=list)


class PluginInstallResolutionService:
    """Resolve user-facing plugin install sources to internal identities."""

    async def resolve(self, source: PluginInstallSource) -> PluginInstallResolution:
        if source.kind == "requirement":
            return self._resolve_requirement(source, source.value or "")
        if source.kind == "store_item":
            return await self._resolve_store_item(source)
        if source.kind == "local_path":
            return self._resolve_local_path(source, source.value or "")
        return PluginInstallResolution(source=source, status="invalid")

    def _resolve_requirement(
        self,
        source: PluginInstallSource,
        requirement: str,
    ) -> PluginInstallResolution:
        target = requirement.strip()
        if not target:
            return PluginInstallResolution(
                source=source,
                status="invalid",
                warnings=["package requirement is required"],
            )
        candidates = [
            self._candidate(module_name, reason="requirement")
            for module_name in resolve_plugin_module_candidates_from_requirement(target)
        ]
        return _resolution_from_candidates(
            source,
            candidates,
            action_kind="install_package",
            requirement=target,
        )

    async def _resolve_store_item(
        self,
        source: PluginInstallSource,
    ) -> PluginInstallResolution:
        source_id = (source.source_id or "").strip()
        item_id = (source.item_id or "").strip()
        if not source_id or not item_id:
            return PluginInstallResolution(
                source=source,
                status="invalid",
                warnings=["store source and item are required"],
            )
        item = await package_store_workflow.get_item(
            PackageStoreItemRequest(
                item_type="plugin",
                source_id=source_id,
                item_id=item_id,
            )
        )
        if item is None:
            return PluginInstallResolution(
                source=source,
                status="invalid",
                warnings=["store item was not found"],
            )
        candidate = self._candidate(
            item.module_name,
            reason="store",
            already_registered=item.is_registered,
            already_loaded=item.is_installed,
        )
        status = "installed" if item.is_installed or item.is_registered else "resolved"
        return PluginInstallResolution(
            source=source,
            status=status,
            candidates=[candidate],
            default_action=PluginInstallAction(
                kind="install_package",
                requirement=item.package_requirement,
                module_name=item.module_name,
            ),
        )

    def _resolve_local_path(
        self,
        source: PluginInstallSource,
        raw_path: str,
    ) -> PluginInstallResolution:
        target = raw_path.strip()
        if not target:
            return PluginInstallResolution(
                source=source,
                status="invalid",
                warnings=["local path is required"],
            )
        path = Path(target).expanduser()
        if not path.is_absolute():
            path = current_project_root() / path
        if not path.exists():
            return PluginInstallResolution(
                source=source,
                status="invalid",
                warnings=["local path does not exist"],
            )
        if path.is_file():
            module_name = path.stem
            return PluginInstallResolution(
                source=source,
                status="resolved",
                candidates=[self._candidate(module_name, reason="local_path")],
                default_action=PluginInstallAction(
                    kind="register_local_module",
                    module_name=module_name,
                    path=target,
                ),
            )
        if (path / "__init__.py").is_file():
            module_name = path.name
            return PluginInstallResolution(
                source=source,
                status="resolved",
                candidates=[self._candidate(module_name, reason="local_path")],
                default_action=PluginInstallAction(
                    kind="register_local_module",
                    module_name=module_name,
                    path=target,
                ),
            )
        return PluginInstallResolution(
            source=source,
            status="resolved",
            default_action=PluginInstallAction(
                kind="register_local_directory",
                path=target,
            ),
        )

    def _candidate(
        self,
        module_name: str,
        *,
        reason: str,
        already_registered: bool | None = None,
        already_loaded: bool = False,
    ) -> PluginInstallCandidate:
        config = plugin_config_service.read_project_plugin_config()
        registered = (
            module_name in config["modules"]
            if already_registered is None
            else already_registered
        )
        return PluginInstallCandidate(
            module_name=module_name,
            confidence="high" if reason in {"store", "local_path"} else "medium",
            reason=reason,
            already_registered=registered,
            already_loaded=already_loaded,
        )


def _resolution_from_candidates(
    source: PluginInstallSource,
    candidates: list[PluginInstallCandidate],
    *,
    action_kind: InstallActionKind,
    requirement: str | None = None,
) -> PluginInstallResolution:
    if len(candidates) == 1:
        candidate = candidates[0]
        status: InstallResolutionStatus = (
            "installed" if candidate.already_registered else "resolved"
        )
        return PluginInstallResolution(
            source=source,
            status=status,
            candidates=candidates,
            default_action=PluginInstallAction(
                kind=action_kind,
                requirement=requirement,
                module_name=candidate.module_name,
            ),
        )
    if len(candidates) > 1:
        return PluginInstallResolution(
            source=source,
            status="ambiguous",
            candidates=candidates,
        )
    return PluginInstallResolution(source=source, status="unresolved")


plugin_install_resolution_service = PluginInstallResolutionService()
