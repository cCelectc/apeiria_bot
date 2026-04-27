from __future__ import annotations

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    ("package_name", "lazy_module_name", "symbol_name"),
    [
        ("apeiria.ai.memory", "apeiria.ai.memory.contracts", "AIMemoryCreateInput"),
        ("apeiria.ai.memory", "apeiria.ai.memory.contracts", "AIMemoryUpdateInput"),
        ("apeiria.ai.memory", "apeiria.ai.memory.service", "ai_memory_service"),
        ("apeiria.ai.model", "apeiria.ai.model.gateway", "model_gateway"),
        ("apeiria.ai.person", "apeiria.ai.person.service", "ai_person_profile_service"),
        ("apeiria.ai.persona", "apeiria.ai.persona.service", "ai_persona_service"),
        (
            "apeiria.ai.relationship",
            "apeiria.ai.relationship.service",
            "ai_relationship_service",
        ),
        (
            "apeiria.ai.relationship",
            "apeiria.ai.relationship.scoring",
            "project_emotion",
        ),
        ("apeiria.ai.skills", "apeiria.ai.skills.service", "ai_skill_service"),
        ("apeiria.ai.tools", "apeiria.ai.tools.gateway", "tool_gateway"),
        (
            "apeiria.ai.tools",
            "apeiria.ai.tools.policy",
            "ai_tool_policy_binding_service",
        ),
        ("apeiria.ai.tools", "apeiria.ai.tools.service", "ai_tool_service"),
    ],
)
def test_stable_ai_root_exports_stay_lazy(
    package_name: str,
    lazy_module_name: str,
    symbol_name: str,
) -> None:
    sys.modules.pop(package_name, None)
    sys.modules.pop(lazy_module_name, None)

    module = importlib.import_module(package_name)

    assert symbol_name in module.__all__
    assert lazy_module_name not in sys.modules

    value = getattr(module, symbol_name)

    assert value is getattr(sys.modules[lazy_module_name], symbol_name)


def test_stable_ai_root_service_exports_stay_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.modules.pop("apeiria.ai.model", None)

    module = importlib.import_module("apeiria.ai.model")
    service_module = importlib.import_module("apeiria.ai.model.service")

    assert module.ai_model_facade is service_module.ai_model_facade

    live_replacement = object()
    monkeypatch.setattr(service_module, "ai_model_facade", live_replacement)

    assert module.ai_model_facade is live_replacement
