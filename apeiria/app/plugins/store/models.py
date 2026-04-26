"""Plugin store models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

StoreItemType = Literal["plugin", "adapter", "driver"]


@dataclass(frozen=True)
class StoreCategoryCount:
    """One normalized category aggregate."""

    value: str
    count: int


@dataclass(frozen=True)
class StoreSource:
    """One normalized store source."""

    source_id: str
    label: str
    kind: str
    enabled: bool = True
    priority: int = 0
    is_builtin: bool = False
    is_official: bool = False
    base_url: str | None = None
    supports_search: bool = True
    supports_exact_lookup: bool = True
    supports_pagination: bool = False
    last_synced_at: str | None = None
    last_error: str | None = None

    @property
    def name(self) -> str:
        return self.label


@dataclass(frozen=True)
class StoreItem:
    """One normalized store item."""

    source_id: str
    item_id: str
    type: StoreItemType
    name: str
    module_name: str
    package_requirement: str
    desc: str | None = None
    project_link: str | None = None
    homepage: str | None = None
    author: str | None = None
    author_link: str | None = None
    version: str | None = None
    tags: list[str] = field(default_factory=list)
    is_official: bool = False
    publish_time: str | None = None
    extra: dict[str, object] = field(default_factory=dict)
    source_label: str = ""
    is_installed: bool = False
    is_registered: bool = False
    installed_package: str | None = None
    installed_module_names: list[str] = field(default_factory=list)
    can_update: bool = False

    @property
    def source_name(self) -> str:
        return self.source_label

    @property
    def plugin_id(self) -> str:
        return self.item_id

    @property
    def package_name(self) -> str:
        return self.package_requirement

    @property
    def description(self) -> str | None:
        return self.desc


@dataclass(frozen=True)
class StoreQuery:
    """Normalized read-only store query."""

    type: StoreItemType = "plugin"
    source_id: str = ""
    keyword: str = ""
    category: str = ""
    sort: str = "default"
    installed_only: bool = False
    uninstalled_only: bool = False
    page: int = 1
    page_size: int = 16

    @property
    def search(self) -> str:
        return self.keyword

    @property
    def per_page(self) -> int:
        return self.page_size


@dataclass(frozen=True)
class StorePage:
    """Paginated store item page."""

    items: list[StoreItem]
    total: int
    page: int
    page_size: int
    has_next: bool = False
    categories: list[StoreCategoryCount] = field(default_factory=list)

    @property
    def per_page(self) -> int:
        return self.page_size


@dataclass(frozen=True)
class StoreInstallCandidate:
    """Install-ready store resolution result."""

    source_id: str
    type: StoreItemType
    display_name: str
    resolved_requirement: str
    binding_hint: str
    item_id: str


@dataclass(frozen=True)
class StoreInstallRequest:
    """Request to install one store item."""

    source_id: str
    item_id: str
    type: StoreItemType = "plugin"
    package_requirement: str = ""
    binding_value: str = ""

    @property
    def plugin_id(self) -> str:
        return self.item_id

    @property
    def package_name(self) -> str:
        return self.package_requirement

    @property
    def module_name(self) -> str:
        return self.binding_value


@dataclass(frozen=True)
class StoreTask:
    """One in-memory store task."""

    task_id: str
    title: str
    status: str
    logs: str
    error: str | None = None
    result: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
