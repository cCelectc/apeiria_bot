from __future__ import annotations

import pytest

from apeiria.ai.model.exceptions import (
    AIModelAuthError,
    AIModelConnectionError,
    AIModelContextLengthError,
    AIModelError,
    AIModelProviderNotFoundError,
    AIModelRateLimitError,
)
from apeiria.ai.model.registry import _provider_registry, get_provider


def test_provider_registry_lookup() -> None:
    import apeiria.ai.model.adapters.anthropic_compatible
    import apeiria.ai.model.adapters.fastembed_adapter
    import apeiria.ai.model.adapters.openai_compatible  # noqa: F401

    assert "openai_compatible" in _provider_registry
    assert "anthropic_compatible" in _provider_registry
    assert "fastembed" in _provider_registry


def test_get_provider_not_found() -> None:
    with pytest.raises(AIModelProviderNotFoundError):
        get_provider("nonexistent", "chat")


def test_unified_exceptions_hierarchy() -> None:
    assert issubclass(AIModelRateLimitError, AIModelError)
    assert issubclass(AIModelAuthError, AIModelError)
    assert issubclass(AIModelContextLengthError, AIModelError)
    assert issubclass(AIModelConnectionError, AIModelError)


def test_provider_capability_registered() -> None:
    import apeiria.ai.model.adapters.openai_compatible  # noqa: F401

    provider = get_provider("openai_compatible", "chat")
    assert provider is not None


def test_provider_not_found_error_message() -> None:
    with pytest.raises(AIModelProviderNotFoundError, match="nonexistent"):
        get_provider("nonexistent", "chat")
