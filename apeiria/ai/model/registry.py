from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")

_provider_registry: dict[str, dict[str, Any]] = {}


def register_provider(name: str) -> Callable[[type[_T]], type[_T]]:
    def decorator(cls: type[_T]) -> type[_T]:
        instance = cls()
        _provider_registry[name] = {}
        for cap in getattr(cls, "capabilities", set()):
            if cap == "chat":
                _provider_registry[name]["chat"] = instance
            elif cap == "embedding":
                _provider_registry[name]["embedding"] = instance
            elif cap == "rerank":
                _provider_registry[name]["rerank"] = instance
        return cls

    return decorator


def get_provider(adapter: str, capability: str) -> Any:
    providers = _provider_registry.get(adapter)
    if not providers:
        from apeiria.ai.model.exceptions import AIModelProviderNotFoundError

        raise AIModelProviderNotFoundError(adapter)
    provider = providers.get(capability)
    if not provider:
        from apeiria.ai.model.exceptions import AIModelCapabilityError

        raise AIModelCapabilityError(adapter, capability)
    return provider
