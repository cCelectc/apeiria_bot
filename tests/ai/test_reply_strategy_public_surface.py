from __future__ import annotations

import importlib
import sys

import pytest


def test_import_app_ai_reply_strategy_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.reply_strategy",
        "apeiria.app.ai.reply_strategy.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.reply_strategy")

    assert module.__name__ == "apeiria.app.ai.reply_strategy"
    assert "reply_strategy_service" in module.__all__
    assert "apeiria.app.ai.reply_strategy.service" not in sys.modules
    assert (
        module.reply_strategy_service
        is sys.modules["apeiria.app.ai.reply_strategy.service"].reply_strategy_service
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.ai.reply_strategy",
        "apeiria.ai.reply_strategy.models",
        "apeiria.ai.reply_strategy.service",
        "apeiria.ai.reply_strategy.social_judgment",
    ],
)
def test_legacy_ai_reply_strategy_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
