from __future__ import annotations

import asyncio
from typing import Any, Literal

MODULE_TYPE = Literal["plugin", "adapter", "driver"]


def _load_handlers() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from nb_cli.cli.utils import find_exact_package, format_package_results
        from nb_cli.handlers.adapter import list_adapters
        from nb_cli.handlers.driver import list_drivers
        from nb_cli.handlers.plugin import list_plugins
    except ModuleNotFoundError as exc:
        raise RuntimeError("nb-cli") from exc

    return (
        list_plugins,
        list_adapters,
        list_drivers,
        format_package_results,
        find_exact_package,
    )


def search_store_packages(
    module_type: MODULE_TYPE,
    query: str | None = None,
) -> list[object]:
    return asyncio.run(search_store_packages_async(module_type, query))


async def search_store_packages_async(
    module_type: MODULE_TYPE,
    query: str | None = None,
) -> list[object]:
    list_plugins, list_adapters, list_drivers, _, _ = _load_handlers()
    if module_type == "plugin":
        return list(await list_plugins(query))
    if module_type == "adapter":
        return list(await list_adapters(query))
    return list(await list_drivers(query))


def find_exact_store_package(
    module_type: MODULE_TYPE,
    value: str,
) -> object | None:
    return asyncio.run(find_exact_store_package_async(module_type, value))


async def find_exact_store_package_async(
    module_type: MODULE_TYPE,
    value: str,
) -> object | None:
    needle = value.lower()
    for item in await search_store_packages_async(module_type, value):
        if any(
            str(candidate).lower() == needle
            for candidate in (
                getattr(item, "name", ""),
                getattr(item, "module_name", ""),
                getattr(item, "project_link", ""),
            )
        ):
            return item
    return None


def format_store_packages(items: list[object]) -> str:
    _, _, _, format_package_results, _ = _load_handlers()
    return str(format_package_results(items))


def prompt_select_store_package(
    module_type: MODULE_TYPE,
    question: str,
    query: str | None = None,
) -> object:
    *_, find_exact_package = _load_handlers()
    items = search_store_packages(module_type, query)
    if not items:
        raise RuntimeError("empty-store")

    if query:
        needle = query.lower()
        for item in items:
            if any(
                str(candidate).strip().lower() == needle
                for candidate in (
                    getattr(item, "name", ""),
                    getattr(item, "module_name", ""),
                    getattr(item, "project_link", ""),
                )
            ):
                return item
        if len(items) == 1:
            return items[0]

    return asyncio.run(find_exact_package(question, None, items))


def prompt_select_text(question: str, items: list[str]) -> str:
    if not items:
        raise RuntimeError("empty-select")
    try:
        from nb_cli.cli.utils import CLI_DEFAULT_STYLE
        from noneprompt import Choice, ListPrompt
    except ModuleNotFoundError as exc:
        raise RuntimeError("nb-cli") from exc

    async def _runner() -> str:
        result = await ListPrompt(
            question,
            [Choice(item, item) for item in items],
        ).prompt_async(style=CLI_DEFAULT_STYLE)
        return str(result.data)

    return asyncio.run(_runner())
