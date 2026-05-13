from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model import (
    AIChatModelDefinition,
    AIModelGenerateResponse,
    AIModelMessage,
    AIModelProfileDefinition,
    AIModelStreamEvent,
    AIModelToolCall,
    AISelectedModel,
    AISourceDefinition,
)
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallOptions,
    parse_model_capabilities,
)
from apeiria.ai.tools.models import AIToolPolicy
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopInput

if TYPE_CHECKING:
    from collections.abc import Mapping

    from apeiria.ai.model.runtime.adapter import AIModelToolDefinition
    from apeiria.ai.tools import AIToolObservationResult


def selected_model(
    suffix: str,
    *,
    fallback_profile_id: str | None = None,
    supports_streaming: bool = False,
) -> AISelectedModel:
    capability_metadata: dict[str, object] = {}
    if supports_streaming:
        capability_metadata["streaming"] = True
    source_model = AIChatModelDefinition(
        model_id=f"model-{suffix}",
        source_id=f"source-{suffix}",
        model_identifier=f"model-{suffix}",
        display_name=f"Model {suffix}",
        capability_metadata=capability_metadata,
    )
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
        source_model=source_model,
        resolved_capabilities=parse_model_capabilities(capability_metadata),
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


class ModelInvokerStub:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[AISelectedModel] = []
        self.stream_calls: list[AISelectedModel] = []
        self.message_calls: list[tuple[AIModelMessage, ...]] = []
        self.tool_calls: list[tuple[AIModelToolDefinition, ...]] = []
        self.option_calls: list[AIModelCallOptions | None] = []

    async def generate_text(
        self,
        *,
        selected: AISelectedModel,
        prompt: str = "",
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[AIModelToolDefinition, ...] = (),
        options: AIModelCallOptions | None = None,
        **_: Any,
    ) -> AIModelGenerateResponse | None:
        del prompt
        self.calls.append(selected)
        self.message_calls.append(messages)
        self.tool_calls.append(tools)
        self.option_calls.append(options)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def stream_text(
        self,
        *,
        selected: AISelectedModel,
        prompt: str = "",
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[AIModelToolDefinition, ...] = (),
        **_: Any,
    ) -> Any:
        del prompt, messages, tools
        self.stream_calls.append(selected)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        for event in outcome:
            yield event


def stream_start(
    selected: AISelectedModel,
    *,
    stream_id: str = "stream-1",
) -> AIModelStreamEvent:
    return AIModelStreamEvent.start(
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or "",
        stream_id=stream_id,
    )


def stream_delta(
    selected: AISelectedModel,
    content_delta: str,
    *,
    stream_id: str = "stream-1",
) -> AIModelStreamEvent:
    return AIModelStreamEvent.text_delta(
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or "",
        stream_id=stream_id,
        content_delta=content_delta,
    )


def stream_final(
    selected: AISelectedModel,
    response: AIModelGenerateResponse,
    *,
    stream_id: str = "stream-1",
) -> AIModelStreamEvent:
    return AIModelStreamEvent.final(
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or "",
        stream_id=stream_id,
        response=response,
    )


@dataclass
class ToolServiceStub:
    observations: list[list[AIToolObservationResult]]
    visible_tool_names: tuple[str, ...] = ("memory.query",)

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
        return [SimpleNamespace(name=name) for name in self.visible_tool_names]

    @property
    def registry(self) -> Any:
        return ToolRegistryStub()


class ToolRegistryStub:
    def list_tools(self) -> list[Any]:
        return []


def tool_loop_input(  # noqa: PLR0913
    selected: AISelectedModel,
    *,
    messages: tuple[AIModelMessage, ...] = (),
    tools: tuple[AIModelToolDefinition, ...] = (),
    fallback_models: tuple[AISelectedModel, ...] = (),
    executable_tool_names: frozenset[str] | None = None,
    provider_name_map: Mapping[str, str] | None = None,
    execution_timeout_seconds: float | None = None,
) -> RuntimeToolLoopInput:
    return RuntimeToolLoopInput(
        session_id="session-1",
        source_message_id="message-1",
        trace_id="trace-tools",
        runtime_mode="message",
        message_text="use tools",
        current_time=datetime.now(timezone.utc),
        selected=selected,
        fallback_models=fallback_models,
        messages=messages,
        tools=tools,
        tool_policy=AIToolPolicy(),
        executable_tool_names=executable_tool_names,
        provider_name_map=provider_name_map,
        recalled_memory_ids=(),
        recalled_memory_contents=(),
        relationship_context=None,
        execution_timeout_seconds=execution_timeout_seconds,
    )


def tool_call(call_id: str, name: str = "memory_query") -> AIModelToolCall:
    return AIModelToolCall(
        tool_call_id=call_id,
        name=name,
        arguments={"query_text": "hello"},
    )
