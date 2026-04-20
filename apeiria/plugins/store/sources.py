"""Plugin store source adapters."""

from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import cast
from urllib.request import urlopen

from apeiria.config import project_config_service
from apeiria.i18n import t
from apeiria.plugins.store.models import (
    StoreInstallCandidate,
    StoreItem,
    StoreItemType,
    StorePage,
    StoreQuery,
    StoreSource,
)
from apeiria.plugins.store.nb_cli import search_store_packages_async


class StoreSourceAdapter(ABC):
    """Abstract source adapter."""

    @abstractmethod
    def source_info(self) -> StoreSource:
        """Return source metadata."""

    @abstractmethod
    async def list_page(self, query: StoreQuery) -> StorePage:
        """Return one normalized page of items."""

    @abstractmethod
    async def find_exact(
        self,
        item_type: StoreItemType,
        value: str,
    ) -> StoreItem | None:
        """Find one exact store item."""

    @abstractmethod
    def resolve_install_candidate(self, item: StoreItem) -> StoreInstallCandidate:
        """Convert one store item into an install-ready candidate."""


class OfficialNoneBotStoreSource(StoreSourceAdapter):
    """Official NoneBot source adapter."""

    def __init__(self) -> None:
        self._last_synced_at = ""
        self._last_error = ""

    def source_info(self) -> StoreSource:
        return StoreSource(
            source_id="official-nonebot",
            label=t("common.store_source_official_nonebot"),
            kind="official-nonebot",
            enabled=True,
            priority=0,
            is_builtin=True,
            is_official=True,
            base_url="https://nonebot.dev/store/plugins",
            supports_search=True,
            supports_exact_lookup=True,
            supports_pagination=False,
            last_synced_at=self._last_synced_at or None,
            last_error=self._last_error or None,
        )

    async def list_page(self, query: StoreQuery) -> StorePage:
        items = await self._load_items(query.type, query.keyword)
        total = len(items)
        return StorePage(
            items=items,
            total=total,
            page=1,
            page_size=total or 1,
            has_next=False,
        )

    async def find_exact(
        self,
        item_type: StoreItemType,
        value: str,
    ) -> StoreItem | None:
        needle = value.strip().lower()
        if not needle:
            return None
        for item in await self._load_items(item_type, value):
            if any(
                candidate.lower() == needle
                for candidate in (
                    item.item_id,
                    item.module_name,
                    item.package_requirement,
                    item.name,
                )
                if candidate
            ):
                return item
        return None

    def resolve_install_candidate(self, item: StoreItem) -> StoreInstallCandidate:
        return StoreInstallCandidate(
            source_id=item.source_id,
            type=item.type,
            display_name=item.name,
            resolved_requirement=item.package_requirement,
            binding_hint=item.module_name,
            item_id=item.item_id,
        )

    async def _load_items(
        self,
        item_type: StoreItemType,
        query: str | None = None,
    ) -> list[StoreItem]:
        try:
            items = await search_store_packages_async(item_type, query)
        except Exception as exc:
            self._last_error = str(exc)
            raise

        now = datetime.now(timezone.utc).isoformat()
        self._last_synced_at = now
        self._last_error = ""
        source = self.source_info()
        normalized: list[StoreItem] = []
        for item in items:
            normalized_item = _normalize_store_item(item, source, item_type)
            if normalized_item is not None:
                normalized.append(normalized_item)
        return normalized


class JsonHttpStoreSource(StoreSourceAdapter):
    """Reserved adapter for future custom HTTP JSON sources."""

    def __init__(
        self,
        source_id: str,
        label: str,
        base_url: str,
        *,
        priority: int = 100,
    ) -> None:
        self._source = StoreSource(
            source_id=source_id,
            label=label,
            kind="json-http",
            enabled=True,
            priority=priority,
            is_builtin=False,
            is_official=False,
            base_url=base_url,
            supports_search=True,
            supports_exact_lookup=True,
            supports_pagination=False,
        )
        self._last_synced_at = ""
        self._last_error = ""

    def source_info(self) -> StoreSource:
        return StoreSource(
            **{
                **self._source.__dict__,
                "last_synced_at": self._last_synced_at or None,
                "last_error": self._last_error or None,
            }
        )

    async def list_page(self, query: StoreQuery) -> StorePage:
        items = await self._load_items(query.type, query.keyword)
        return StorePage(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items) or 1,
            has_next=False,
        )

    async def find_exact(
        self,
        item_type: StoreItemType,
        value: str,
    ) -> StoreItem | None:
        needle = value.strip().lower()
        if not needle:
            return None
        for item in await self._load_items(item_type):
            if any(
                candidate.lower() == needle
                for candidate in (
                    item.item_id,
                    item.module_name,
                    item.package_requirement,
                    item.name,
                )
                if candidate
            ):
                return item
        return None

    def resolve_install_candidate(self, item: StoreItem) -> StoreInstallCandidate:
        return StoreInstallCandidate(
            source_id=item.source_id,
            type=item.type,
            display_name=item.name,
            resolved_requirement=item.package_requirement,
            binding_hint=item.module_name,
            item_id=item.item_id,
        )

    async def _load_items(
        self,
        item_type: StoreItemType,
        query: str | None = None,
    ) -> list[StoreItem]:
        try:
            payload = await asyncio.to_thread(
                _load_json_http_payload,
                self._source.base_url,
            )
        except Exception as exc:
            self._last_error = str(exc)
            raise

        now = datetime.now(timezone.utc).isoformat()
        self._last_synced_at = now
        self._last_error = ""
        items = payload.get("items", [])
        if not isinstance(items, list):
            return []

        normalized: list[StoreItem] = []
        keyword = (query or "").strip().lower()
        for item in items:
            normalized_item = _normalize_json_http_item(
                item,
                self.source_info(),
                item_type,
            )
            if normalized_item is None:
                continue
            if (
                keyword
                and keyword
                not in " ".join(
                    [
                        normalized_item.name,
                        normalized_item.module_name,
                        normalized_item.package_requirement,
                        normalized_item.desc or "",
                        normalized_item.author or "",
                        " ".join(normalized_item.tags),
                    ]
                ).lower()
            ):
                continue
            normalized.append(normalized_item)
        return normalized


def configured_store_sources() -> list[StoreSourceAdapter]:
    sources: list[StoreSourceAdapter] = [OfficialNoneBotStoreSource()]
    for item in project_config_service.read_plugin_store_sources_config():
        source_id = str(item.get("source_id", "")).strip()
        if not source_id:
            continue
        enabled = bool(item.get("enabled", True))
        if not enabled:
            continue
        kind = str(item.get("kind", "")).strip()
        label = str(item.get("label", source_id)).strip() or source_id
        base_url = str(item.get("base_url", "")).strip()
        if kind == "json-http" and base_url:
            sources.append(
                JsonHttpStoreSource(
                    source_id=source_id,
                    label=label,
                    base_url=base_url,
                    priority=_read_priority(item.get("priority")),
                )
            )
    return sources


def _normalize_store_item(
    item: object,
    source: StoreSource,
    item_type: StoreItemType,
) -> StoreItem | None:
    module_name = _read_str_attr(item, "module_name")
    package_requirement = _read_package_requirement(item)
    name = _read_str_attr(item, "name") or module_name or package_requirement
    if not module_name or not package_requirement or not name:
        return None

    desc = (
        _read_str_attr(item, "desc")
        or _read_str_attr(item, "description")
        or _read_str_attr(item, "summary")
        or None
    )
    raw_project_link = _read_str_attr(item, "project_link")
    homepage = _normalize_external_url(_read_str_attr(item, "homepage"))
    project_link = _normalize_external_url(raw_project_link) or homepage
    author = _read_str_attr(item, "author") or None
    author_link = _read_author_link(item)
    version = (
        _read_str_attr(item, "latest_version")
        or _read_str_attr(item, "version")
        or None
    )
    tags = _read_tags(item)
    extra = _read_extra(item)
    publish_time = _read_publish_time(item)

    return StoreItem(
        source_id=source.source_id,
        source_label=source.label,
        item_id=module_name,
        type=item_type,
        name=name,
        module_name=module_name,
        package_requirement=package_requirement,
        desc=desc,
        project_link=project_link,
        homepage=homepage,
        author=author,
        author_link=author_link,
        version=version,
        tags=tags,
        is_official=source.is_official,
        publish_time=publish_time,
        extra=extra,
    )


def _read_package_requirement(item: object) -> str:
    project_link = _read_str_attr(item, "project_link")
    if project_link:
        return project_link

    as_dependency = getattr(item, "as_dependency", None)
    if callable(as_dependency):
        dependency = as_dependency()
        if isinstance(dependency, str) and dependency.strip():
            return dependency.strip()
    return ""


def _read_tags(item: object) -> list[str]:
    raw = getattr(item, "tags", None)
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for tag in raw:
        parsed = _normalize_tag(str(tag))
        if parsed:
            normalized.append(parsed)
    return normalized


def _read_publish_time(item: object) -> str | None:
    for attr in ("publish_time", "updated_at", "time"):
        value = getattr(item, attr, None)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _read_author_link(item: object) -> str | None:
    for attr in ("author_link", "author_url", "author_homepage", "author_repo"):
        value = _normalize_external_url(_read_str_attr(item, attr))
        if value is not None:
            return value
    return None


def _read_extra(item: object) -> dict[str, object]:
    keys = getattr(item, "__dict__", {})
    if not isinstance(keys, dict):
        return {}
    excluded = {
        "name",
        "module_name",
        "project_link",
        "desc",
        "description",
        "summary",
        "author",
        "homepage",
        "latest_version",
        "version",
        "tags",
    }
    return {
        key: value
        for key, value in keys.items()
        if key not in excluded and value is not None
    }


def _read_str_attr(item: object, attr: str) -> str:
    value = getattr(item, attr, "")
    return value.strip() if isinstance(value, str) else ""


def _normalize_external_url(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://")):
        return normalized
    return None


def _normalize_tag(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    label_match = re.search(r"label=(['\"])(.*?)\1", normalized)
    if label_match:
        return label_match.group(2).strip()
    if " color=" in normalized:
        normalized = normalized.split(" color=", 1)[0].strip()
    if normalized.startswith("label="):
        normalized = normalized[6:].strip().strip("'\"")
    return normalized


def _normalize_json_http_item(
    item: object,
    source: StoreSource,
    item_type: StoreItemType,
) -> StoreItem | None:
    if not isinstance(item, dict):
        return None
    normalized_type = _read_store_item_type(item.get("type"))
    if normalized_type != item_type:
        return None

    module_name = _read_mapping_str(item, "module_name")
    package_requirement = _read_mapping_str(item, "package_requirement")
    name = _read_mapping_str(item, "name") or module_name or package_requirement
    if not module_name or not package_requirement or not name:
        return None

    raw_tags = item.get("tags", [])
    tags = (
        [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        if isinstance(raw_tags, list)
        else []
    )

    extra = {
        key: value
        for key, value in item.items()
        if key
        not in {
            "type",
            "item_id",
            "name",
            "module_name",
            "package_requirement",
            "desc",
            "project_link",
            "homepage",
            "author",
            "author_link",
            "version",
            "tags",
            "publish_time",
        }
    }

    return StoreItem(
        source_id=source.source_id,
        source_label=source.label,
        item_id=_read_mapping_str(item, "item_id") or module_name,
        type=normalized_type,
        name=name,
        module_name=module_name,
        package_requirement=package_requirement,
        desc=_read_mapping_str(item, "desc") or None,
        project_link=_normalize_external_url(_read_mapping_str(item, "project_link")),
        homepage=_normalize_external_url(_read_mapping_str(item, "homepage")),
        author=_read_mapping_str(item, "author") or None,
        author_link=_normalize_external_url(_read_mapping_str(item, "author_link")),
        version=_read_mapping_str(item, "version") or None,
        tags=tags,
        is_official=source.is_official,
        publish_time=_read_mapping_str(item, "publish_time") or None,
        extra=extra,
    )


def _read_mapping_str(item: dict[str, object], key: str) -> str:
    value = item.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _read_priority(value: object) -> int:
    return value if isinstance(value, int) else 100


def _read_store_item_type(value: object) -> StoreItemType:
    if isinstance(value, str) and value in {"plugin", "adapter", "driver"}:
        return cast("StoreItemType", value)
    return "plugin"


def _load_json_http_payload(base_url: str | None) -> dict[str, object]:
    if not base_url:
        msg = "json-http source base_url is required"
        raise ValueError(msg)
    with urlopen(base_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        msg = "json-http source response must be an object"
        raise TypeError(msg)
    return payload
