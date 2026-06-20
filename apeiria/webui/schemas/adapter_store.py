"""Adapter package store Web UI schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.plugins.store.models import StoreItem


class AdapterStoreSourceItem(BaseModel):
    source_id: str
    name: str
    kind: str
    enabled: bool = True
    is_builtin: bool = False
    is_official: bool = False
    base_url: str | None = None
    last_synced_at: str | None = None
    last_error: str | None = None


class AdapterStoreItem(BaseModel):
    source_id: str
    source_name: str
    adapter_id: str
    name: str
    module_name: str
    package_name: str
    description: str | None = None
    project_link: str | None = None
    homepage: str | None = None
    author: str | None = None
    author_link: str | None = None
    version: str | None = None
    tags: list[str] = []
    is_official: bool = False
    publish_time: str | None = None
    extra: dict[str, object] = {}
    is_installed: bool = False
    is_registered: bool = False
    installed_package: str | None = None
    installed_module_names: list[str] = []
    can_update: bool = False


class AdapterStoreCategoryItem(BaseModel):
    value: str
    count: int


class AdapterStoreItemsResponse(BaseModel):
    items: list[AdapterStoreItem]
    categories: list[AdapterStoreCategoryItem] = []
    total: int
    page: int
    per_page: int


class AdapterStoreMutationRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    adapter_id: str = Field(min_length=1, max_length=256)
    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class AdapterStoreManualInstallRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=512)
    module_name: str | None = Field(default=None, max_length=256)


class AdapterStoreUninstallRequest(BaseModel):
    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class AdapterStoreRevertInstallRequest(BaseModel):
    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class AdapterStoreTaskItem(BaseModel):
    task_id: str
    title: str
    status: str
    logs: str
    error: str | None = None
    result: dict[str, object] = {}
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    operation: str | None = None
    resource_kind: str | None = None
    requirement: str | None = None
    binding_value: str | None = None
    current_phase: str | None = None
    current_phase_label: str | None = None
    progress_percent: int | None = None
    queue_position: int | None = None
    lock_wait_started_at: str | None = None
    lock_acquired_at: str | None = None
    restart_required: bool = False
    steps: list[dict[str, object | None]] = []
    diagnostics: list[dict[str, object]] = []


def to_adapter_store_source_item(item: Any) -> AdapterStoreSourceItem:
    return AdapterStoreSourceItem(
        source_id=item.source_id,
        name=item.name,
        kind=item.kind,
        enabled=item.enabled,
        is_builtin=item.is_builtin,
        is_official=item.is_official,
        base_url=item.base_url,
        last_synced_at=item.last_synced_at,
        last_error=item.last_error,
    )


def to_adapter_store_item(item: "StoreItem") -> AdapterStoreItem:
    return AdapterStoreItem(
        source_id=item.source_id,
        source_name=item.source_name,
        adapter_id=item.item_id,
        name=item.name,
        module_name=item.module_name,
        package_name=item.package_name,
        description=item.description,
        project_link=item.project_link,
        homepage=item.homepage,
        author=item.author,
        author_link=item.author_link,
        version=item.version,
        tags=item.tags,
        is_official=item.is_official,
        publish_time=item.publish_time,
        extra=item.extra,
        is_installed=item.is_installed,
        is_registered=item.is_registered,
        installed_package=item.installed_package,
        installed_module_names=item.installed_module_names,
        can_update=item.can_update,
    )


def to_adapter_store_task_item(task: Any) -> AdapterStoreTaskItem:
    return AdapterStoreTaskItem(
        task_id=task.task_id,
        title=task.title,
        status=task.status,
        logs=task.logs,
        error=task.error,
        result=task.result,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        operation=getattr(task, "operation", None),
        resource_kind=getattr(task, "resource_kind", None),
        requirement=getattr(task, "requirement", None),
        binding_value=getattr(task, "binding_value", None),
        current_phase=getattr(task, "current_phase", None),
        current_phase_label=getattr(task, "current_phase_label", None),
        progress_percent=getattr(task, "progress_percent", None),
        queue_position=getattr(task, "queue_position", None),
        lock_wait_started_at=getattr(task, "lock_wait_started_at", None),
        lock_acquired_at=getattr(task, "lock_acquired_at", None),
        restart_required=bool(getattr(task, "restart_required", False)),
        steps=[_task_step_payload(step) for step in getattr(task, "steps", ())],
        diagnostics=list(getattr(task, "diagnostics", ())),
    )


def _task_step_payload(step: Any) -> dict[str, object | None]:
    return {
        "phase": getattr(step, "phase", None),
        "label": getattr(step, "label", None),
        "status": getattr(step, "status", None),
        "detail": getattr(step, "detail", None),
        "command": getattr(step, "command", None),
        "output_excerpt": getattr(step, "output_excerpt", None),
        "started_at": getattr(step, "started_at", None),
        "finished_at": getattr(step, "finished_at", None),
    }
