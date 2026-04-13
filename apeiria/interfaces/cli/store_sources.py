from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

from .nb import (
    MODULE_TYPE,
    find_exact_store_package,
    format_store_packages,
    prompt_select_store_package,
    search_store_packages,
)

DEFAULT_STORE_SOURCE_ID = "official-nonebot"
DEFAULT_STORE_SOURCE_LABEL = "NoneBot2"


class CliStoreSource(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def aliases(self) -> tuple[str, ...]: ...

    @property
    def label(self) -> str: ...

    def search(
        self,
        module_type: MODULE_TYPE,
        query: str | None = None,
    ) -> list[object]:
        """Search source items."""
        ...

    def find_exact(self, module_type: MODULE_TYPE, value: str) -> object | None:
        """Find one exact source item."""
        ...

    def prompt_select(
        self,
        module_type: MODULE_TYPE,
        question: str,
        query: str | None = None,
    ) -> object:
        """Prompt user to select one source item."""
        ...

    def format_items(self, items: list[object]) -> str:
        """Render source items for CLI output."""
        ...


@dataclass(frozen=True)
class NoneBotCliStoreSource:
    source_id: Final[str] = DEFAULT_STORE_SOURCE_ID
    aliases: Final[tuple[str, ...]] = ("nonebot2", "nonebot", "official-nonebot")
    label: Final[str] = DEFAULT_STORE_SOURCE_LABEL

    def search(
        self,
        module_type: MODULE_TYPE,
        query: str | None = None,
    ) -> list[object]:
        return search_store_packages(module_type, query)

    def find_exact(self, module_type: MODULE_TYPE, value: str) -> object | None:
        return find_exact_store_package(module_type, value)

    def prompt_select(
        self,
        module_type: MODULE_TYPE,
        question: str,
        query: str | None = None,
    ) -> object:
        return prompt_select_store_package(module_type, question, query)

    def format_items(self, items: list[object]) -> str:
        return format_store_packages(items)


_CLI_STORE_SOURCES: tuple[CliStoreSource, ...] = (NoneBotCliStoreSource(),)


def default_store_source_id() -> str:
    return DEFAULT_STORE_SOURCE_ID


def resolve_cli_store_source(source_id: str | None = None) -> CliStoreSource:
    normalized = (source_id or DEFAULT_STORE_SOURCE_ID).strip().lower()
    for source in _CLI_STORE_SOURCES:
        if normalized == source.source_id or normalized in source.aliases:
            return source
    msg = f"unknown store source: {source_id}"
    raise RuntimeError(msg)
