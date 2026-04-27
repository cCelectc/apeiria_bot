from __future__ import annotations

import importlib
import sys

import pytest


def test_import_apeiria_ai_does_not_eagerly_import_runtime_services() -> None:
    for module_name in (
        "apeiria.ai",
        "apeiria.conversation.service",
        "apeiria.ai.memory.service",
        "apeiria.ai.model.runtime.gateway",
        "apeiria.ai.person.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.relationship.service",
        "apeiria.app.ai.reply_strategy.service",
        "apeiria.ai.retention",
        "apeiria.ai.service",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.ai")

    assert module.__name__ == "apeiria.ai"
    assert module.__all__ == [
        "AIService",
        "AIServiceStatus",
        "ai_memory_service",
        "ai_person_profile_service",
        "ai_persona_service",
        "ai_relationship_service",
        "ai_retention_service",
        "ai_service",
        "ai_skill_service",
        "ai_tool_service",
        "model_gateway",
        "tool_gateway",
    ]

    for module_name in (
        "apeiria.conversation.service",
        "apeiria.ai.memory.service",
        "apeiria.ai.model.runtime.gateway",
        "apeiria.ai.person.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.relationship.service",
        "apeiria.app.ai.reply_strategy.service",
        "apeiria.ai.retention",
        "apeiria.ai.service",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        assert module_name not in sys.modules

    ai_service = module.ai_service

    assert ai_service is sys.modules["apeiria.ai.service"].ai_service


def test_apeiria_ai_no_longer_re_exports_conversation_core() -> None:
    module = importlib.import_module("apeiria.ai")

    assert not hasattr(module, "chat_session_service")
    assert not hasattr(module, "ai_future_task_service")
    assert not hasattr(module, "reply_strategy_service")


def test_ai_service_status_reports_active_runtime() -> None:
    module = importlib.import_module("apeiria.ai.service")
    status = module.ai_service.get_status()
    expected_summary = (
        "AI plugin is active across runtime messaging, memory, tools, "
        "admin, and session-read surfaces."
    )

    assert status.phase == "runtime_active"
    assert status.summary == expected_summary


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.ai.conversation",
        "apeiria.ai.conversation.identity",
        "apeiria.ai.conversation.models",
        "apeiria.ai.conversation.service",
    ],
)
def test_legacy_ai_conversation_core_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
