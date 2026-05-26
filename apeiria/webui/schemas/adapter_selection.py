"""Adapter selection Web UI schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AdapterSelectionStateName = Literal[
    "available",
    "installed",
    "enabled_pending_restart",
    "enabled_loaded",
    "unavailable",
]


class AdapterSelectionItem(BaseModel):
    source_id: str | None = None
    source_name: str | None = None
    adapter_id: str | None = None
    module_name: str
    display_name: str
    package_name: str | None = None
    description: str | None = None
    homepage: str | None = None
    project_link: str | None = None
    tags: list[str] = []
    is_official: bool = False
    is_installed: bool = False
    is_enabled: bool = False
    is_loaded: bool = False
    is_importable: bool = False
    is_configurable: bool = False
    installed_package: str | None = None
    installed_module_names: list[str] = []
    can_update: bool = False
    state: AdapterSelectionStateName = "available"


class AdapterSelectionSummary(BaseModel):
    enabled: int = 0
    loaded: int = 0
    unavailable: int = 0
    restart_required: int = 0


class AdapterSelectionResponse(BaseModel):
    enabled_adapters: list[AdapterSelectionItem]
    candidates: list[AdapterSelectionItem]
    summary: AdapterSelectionSummary
    total_candidates: int
    page: int
    per_page: int


class AdapterSelectionQueryParams(BaseModel):
    source: str = ""
    search: str = ""
    category: str = ""
    sort: str = "default"
    unenabled_only: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=16, ge=1, le=100)


class AdapterSelectionEnableRequest(BaseModel):
    module_name: str = Field(min_length=1, max_length=256)


def to_adapter_selection_response(state: Any) -> AdapterSelectionResponse:
    return AdapterSelectionResponse(
        enabled_adapters=[
            _to_adapter_selection_item(item) for item in state.enabled_adapters
        ],
        candidates=[_to_adapter_selection_item(item) for item in state.candidates],
        summary=AdapterSelectionSummary(
            enabled=state.summary.enabled,
            loaded=state.summary.loaded,
            unavailable=state.summary.unavailable,
            restart_required=state.summary.restart_required,
        ),
        total_candidates=state.total_candidates,
        page=state.page,
        per_page=state.per_page,
    )


def to_adapter_selection_item(item: Any) -> AdapterSelectionItem:
    return _to_adapter_selection_item(item)


def _to_adapter_selection_item(item: Any) -> AdapterSelectionItem:
    return AdapterSelectionItem(
        source_id=item.source_id,
        source_name=item.source_name,
        adapter_id=item.adapter_id,
        module_name=item.module_name,
        display_name=item.display_name,
        package_name=item.package_name,
        description=item.description,
        homepage=item.homepage,
        project_link=item.project_link,
        tags=list(item.tags or []),
        is_official=item.is_official,
        is_installed=item.is_installed,
        is_enabled=item.is_enabled,
        is_loaded=item.is_loaded,
        is_importable=item.is_importable,
        is_configurable=item.is_configurable,
        installed_package=item.installed_package,
        installed_module_names=list(item.installed_module_names or []),
        can_update=item.can_update,
        state=item.state,
    )
