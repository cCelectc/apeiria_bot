from __future__ import annotations

import time
from typing import Any, Protocol

import httpx
from nonebot.log import logger

_start_time = time.monotonic()

REGISTRY_BASE = "https://registry.nonebot.dev"
_CACHE_TTL = 300.0


def _registry_url(kind: str) -> str:
    return f"{REGISTRY_BASE}/{kind}.json"


class StoreItem:
    __slots__ = (
        "author",
        "description",
        "homepage",
        "installed_version",
        "is_official",
        "module_names",
        "name",
        "pypi_name",
        "supported_adapters",
        "tags",
        "type",
        "version",
    )

    def __init__(  # noqa: PLR0913
        self,
        name: str,
        version: str = "",
        description: str = "",
        author: str = "",
        homepage: str = "",
        pypi_name: str = "",
        module_names: list[str] | None = None,
        supported_adapters: list[str] | None = None,
        installed_version: str | None = None,
        *,
        type: str = "",  # noqa: A002
        tags: list[dict[str, Any]] | None = None,
        is_official: bool = False,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.homepage = homepage
        self.pypi_name = pypi_name
        self.module_names = module_names or []
        self.supported_adapters = supported_adapters
        self.installed_version = installed_version
        self.type = type
        self.tags = tags or []
        self.is_official = is_official

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "pypi_name": self.pypi_name,
            "module_names": self.module_names,
            "supported_adapters": self.supported_adapters,
            "installed_version": self.installed_version,
            "type": self.type,
            "tags": self.tags,
            "is_official": self.is_official,
        }


def _parse_item(raw: dict[str, Any]) -> StoreItem:
    module_name = raw.get("module_name")
    module_names = (
        [module_name] if isinstance(module_name, str) else raw.get("module_names") or []
    )
    return StoreItem(
        name=raw.get("name", ""),
        version=raw.get("version", ""),
        description=raw.get("desc", raw.get("description", "")),
        author=raw.get("author", ""),
        homepage=raw.get("homepage", ""),
        pypi_name=raw.get("project_link", raw.get("pypi_name", "")),
        module_names=module_names,
        supported_adapters=raw.get("supported_adapters"),
        type=raw.get("type", ""),
        tags=raw.get("tags") or [],
        is_official=bool(raw.get("is_official", False)),
    )


def _matches(item: StoreItem, query: str) -> bool:
    if not query:
        return True
    needle = query.lower()
    haystack = " ".join(
        [
            item.name,
            item.description,
            item.author,
            item.pypi_name,
            *item.module_names,
            *(str(t.get("label", "")) for t in item.tags),
        ]
    ).lower()
    return needle in haystack


def paginate(
    items: list[Any],
    offset: int = 0,
    limit: int = 60,
    sort: str = "",
) -> tuple[list[Any], int]:
    if sort == "name_asc":
        items = sorted(items, key=lambda it: (getattr(it, "name", "") or "").lower())
    elif sort == "name_desc":
        items = sorted(
            items,
            key=lambda it: (getattr(it, "name", "") or "").lower(),
            reverse=True,
        )
    else:
        items = sorted(
            items,
            key=lambda it: (
                not getattr(it, "is_official", False),
                (getattr(it, "name", "") or "").lower(),
            ),
        )
    total = len(items)
    if limit <= 0:
        return items[offset:], total
    return items[offset : offset + limit], total


class StoreSource(Protocol):
    async def search(self, query: str) -> list[StoreItem]: ...
    async def get(self, pkg_name: str) -> StoreItem | None: ...


class NoneBotStoreSource:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def _fetch(self, kind: str) -> list[dict[str, Any]]:
        cached = self._cache.get(kind)
        if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL:
            return cached[1]
        url = _registry_url(kind)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        items = data if isinstance(data, list) else data.get(kind, [])
        items = [it for it in items if isinstance(it, dict)]
        self._cache[kind] = (time.monotonic(), items)
        return items

    async def _search_kind(self, kind: str, query: str) -> list[StoreItem]:
        try:
            raw_items = await self._fetch(kind)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to fetch store {kind}: {exc!r}")
            return []
        parsed = [_parse_item(it) for it in raw_items]
        return [it for it in parsed if _matches(it, query)]

    async def search(self, query: str) -> list[StoreItem]:
        return await self._search_kind("plugins", query)

    async def search_adapters(self, query: str) -> list[StoreItem]:
        return await self._search_kind("adapters", query)

    async def get(self, pkg_name: str) -> StoreItem | None:
        items = await self.search(pkg_name)
        for item in items:
            if pkg_name in (item.name, item.pypi_name):
                return item
        return None


_default_store = NoneBotStoreSource()


def get_store() -> NoneBotStoreSource:
    return _default_store


def get_uptime() -> float:
    return time.monotonic() - _start_time


def get_status() -> dict[str, Any]:
    import nonebot

    return {
        "uptime": get_uptime(),
        "plugin_count": len(nonebot.get_loaded_plugins()),
        "adapters": [type(a).__name__ for a in nonebot.get_driver()._adapters.values()],
    }
