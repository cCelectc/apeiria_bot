"""Plugin store Web UI schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.app.plugins.store.models import StoreItem


class PluginStoreSourceItem(BaseModel):
    source_id: str
    name: str
    kind: str
    enabled: bool = True
    is_builtin: bool = False
    is_official: bool = False
    base_url: str | None = None
    last_synced_at: str | None = None
    last_error: str | None = None


class PluginStoreItem(BaseModel):
    source_id: str
    source_name: str
    plugin_id: str
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


class PluginStoreCategoryItem(BaseModel):
    value: str
    count: int


class PluginStoreItemsResponse(BaseModel):
    items: list[PluginStoreItem]
    categories: list[PluginStoreCategoryItem] = []
    total: int
    page: int
    per_page: int


class PluginStoreInstallRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    plugin_id: str = Field(min_length=1, max_length=256)
    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class PluginStoreRevertInstallRequest(BaseModel):
    package_name: str = Field(min_length=1, max_length=256)
    module_name: str = Field(min_length=1, max_length=256)


class PluginStoreTaskItem(BaseModel):
    task_id: str
    title: str
    status: str
    logs: str
    error: str | None = None
    result: dict[str, object] = {}
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


def to_plugin_store_source_item(item: Any) -> PluginStoreSourceItem:
    return PluginStoreSourceItem(
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


def to_plugin_store_item(item: "StoreItem") -> PluginStoreItem:
    return PluginStoreItem(
        source_id=item.source_id,
        source_name=item.source_name,
        plugin_id=item.plugin_id,
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


def to_plugin_store_task_item(task: Any) -> PluginStoreTaskItem:
    return PluginStoreTaskItem(
        task_id=task.task_id,
        title=task.title,
        status=task.status,
        logs=task.logs,
        error=task.error,
        result=task.result,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )
