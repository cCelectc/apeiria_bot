from __future__ import annotations

import importlib
import sys


def test_import_apeiria_ai_does_not_eagerly_import_runtime_services() -> None:
    for module_name in (
        "apeiria.ai",
        "apeiria.ai.conversation.service",
        "apeiria.ai.future_task.service",
        "apeiria.ai.memory.service",
        "apeiria.ai.model.gateway",
        "apeiria.ai.person.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.relationship.service",
        "apeiria.ai.reply_strategy.service",
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
        "ai_future_task_service",
        "ai_memory_service",
        "ai_person_profile_service",
        "ai_persona_service",
        "ai_relationship_service",
        "ai_retention_service",
        "ai_service",
        "ai_skill_service",
        "ai_tool_service",
        "chat_session_service",
        "model_gateway",
        "reply_strategy_service",
        "tool_gateway",
    ]

    for module_name in (
        "apeiria.ai.conversation.service",
        "apeiria.ai.future_task.service",
        "apeiria.ai.memory.service",
        "apeiria.ai.model.gateway",
        "apeiria.ai.person.service",
        "apeiria.ai.persona.service",
        "apeiria.ai.relationship.service",
        "apeiria.ai.reply_strategy.service",
        "apeiria.ai.retention",
        "apeiria.ai.service",
        "apeiria.ai.skills.service",
        "apeiria.ai.tools.gateway",
        "apeiria.ai.tools.service",
    ):
        assert module_name not in sys.modules

    ai_service = module.ai_service

    assert ai_service is sys.modules["apeiria.ai.service"].ai_service
