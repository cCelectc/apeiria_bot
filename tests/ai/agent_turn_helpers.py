from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model import (
    AIModelGenerateResponse,
    AIModelMessage,
    AIModelProfileDefinition,
    AIModelToolCall,
    AISelectedModel,
    AISourceDefinition,
)
from apeiria.ai.tools import AIToolObservationResult, ToolGatewayRequest
from apeiria.ai.tools.models import AIToolPolicy

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelToolDefinition


def selected_model(
    suffix: str,
    *,
    fallback_profile_id: str | None = None,
) -> AISelectedModel:
    return AISelectedModel(
        source=AISourceDefinition(
            source_id=f"source-{suffix}",
            name=f"Source {suffix}",
            capability_type="chat_completion",
            client_type="openai",
            preset_type="openai_compatible",
            api_base="https://example.invalid/v1",
        ),
        profile=AIModelProfileDefinition(
            profile_id=f"profile-{suffix}",
            name=f"Profile {suffix}",
            model_id=f"model-{suffix}",
            task_class="reply_default",
            priority=10,
            fallback_profile_id=fallback_profile_id,
        ),
        resolved_model_name=f"model-{suffix}",
    )


def model_response(
    selected: AISelectedModel,
    content: str,
    *,
    tool_calls: tuple[AIModelToolCall, ...] = (),
) -> AIModelGenerateResponse:
    return AIModelGenerateResponse(
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or "",
        content=content,
        tool_calls=tool_calls,
        raw={"usage": {"prompt_tokens": 12}},
    )


class ModelGatewayStub:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[AISelectedModel] = []
        self.message_calls: list[tuple[AIModelMessage, ...]] = []
        self.tool_calls: list[tuple[AIModelToolDefinition, ...]] = []

    async def generate_native(
        self,
        *,
        selected: AISelectedModel,
        prompt: str = "",
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[AIModelToolDefinition, ...] = (),
        **_: Any,
    ) -> AIModelGenerateResponse | None:
        del prompt
        self.calls.append(selected)
        self.message_calls.append(messages)
        self.tool_calls.append(tools)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass
class ToolServiceStub:
    observations: list[list[AIToolObservationResult]]
    allowed_tool_names: tuple[str, ...] = ("memory.query",)

    def __post_init__(self) -> None:
        self.calls: list[object] = []

    async def execute_tool_intents(
        self,
        *,
        request: object,
        intents: list[object],
    ) -> list[AIToolObservationResult]:
        del request
        self.calls.append(tuple(intents))
        return self.observations.pop(0)

    def build_tool_turns(
        self,
        observations: list[AIToolObservationResult],
    ) -> list[Any]:
        del observations
        return []

    def list_allowed_tools(self, _policy: AIToolPolicy) -> list[Any]:
        return [SimpleNamespace(name=name) for name in self.allowed_tool_names]

    @property
    def registry(self) -> Any:
        return ToolRegistryStub()


class ToolRegistryStub:
    def list_tools(self) -> list[Any]:
        return []


def tool_request() -> ToolGatewayRequest:
    return ToolGatewayRequest(
        session_id="session-1",
        source_message_id="message-1",
        trace_id="trace-tools",
        message_text="use tools",
        policy=AIToolPolicy(execution_enabled=True),
        recalled_memories=(),
        relationship_context=None,
        current_time=datetime.now(timezone.utc),
    )


def tool_call(call_id: str, name: str = "memory_query") -> AIModelToolCall:
    return AIModelToolCall(
        tool_call_id=call_id,
        name=name,
        arguments={"query_text": "hello"},
    )
