from __future__ import annotations

import json
import time
from typing import Any, Protocol

import httpx

_start_time = time.monotonic()


class StoreItem:
    __slots__ = (
        "author",
        "description",
        "homepage",
        "installed_version",
        "module_names",
        "name",
        "pypi_name",
        "supported_adapters",
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
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.homepage = homepage
        self.pypi_name = pypi_name or name
        self.module_names = module_names or []
        self.supported_adapters = supported_adapters or []
        self.installed_version = installed_version

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
        }


class StoreSource(Protocol):
    async def search(self, query: str) -> list[StoreItem]: ...
    async def get(self, pkg_name: str) -> StoreItem | None: ...


class NoneBotStoreSource:
    def __init__(self) -> None:
        self._base_url = "https://nonebot.dev"

    async def search(self, query: str) -> list[StoreItem]:
        url = f"{self._base_url}/store/plugins.json"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                results: list[StoreItem] = []
                for item in data if isinstance(data, list) else data.get("plugins", []):
                    if not isinstance(item, dict):
                        continue
                    if query and query.lower() not in (
                        json.dumps(item, ensure_ascii=False).lower()
                    ):
                        continue
                    results.append(
                        StoreItem(
                            name=item.get("name", ""),
                            version=item.get("version", ""),
                            description=item.get("description", ""),
                            author=item.get("author", ""),
                            homepage=item.get("homepage", ""),
                            pypi_name=item.get("pypi_name", ""),
                            module_names=item.get("module_names", []),
                            supported_adapters=item.get("supported_adapters", []),
                        )
                    )
                return results
        except Exception:  # noqa: BLE001
            return []

    async def get(self, pkg_name: str) -> StoreItem | None:
        items = await self.search(pkg_name)
        for item in items:
            if item.name in (pkg_name, item.pypi_name):
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
