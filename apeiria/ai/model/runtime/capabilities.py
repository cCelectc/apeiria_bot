"""Provider capability contracts for model runtime planning."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, TypeAlias

AIModelAdapterKind: TypeAlias = Literal[
    "openai_compatible",
    "anthropic_compatible",
    "generic_rerank",
]
AIModelCapabilityLane: TypeAlias = Literal[
    "chat_completion",
    "embedding",
    "speech_to_text",
    "text_to_speech",
    "rerank",
]
AIModelContentModality: TypeAlias = Literal[
    "text",
    "image",
    "audio",
    "file",
    "tool_result",
    "provider_data",
]
AIModelToolCallingRequirement: TypeAlias = Literal["required", "optional", "none"]
AIModelStreamingRequirement: TypeAlias = Literal["required", "optional", "none"]
AIModelCallAction: TypeAlias = Literal["invoke", "reject"]
AIModelResponseFormatType: TypeAlias = Literal["json_object", "json_schema"]
AI_MODEL_RESPONSE_FORMAT_OPTION = "response_format"

_KNOWN_LANES = frozenset(
    {
        "chat_completion",
        "embedding",
        "speech_to_text",
        "text_to_speech",
        "rerank",
    }
)
_KNOWN_MODALITIES = frozenset(
    {"text", "image", "audio", "file", "tool_result", "provider_data"}
)


@dataclass(frozen=True)
class AIModelCapabilities:
    """Normalized model capability metadata.

    Empty or unknown provider metadata resolves to conservative defaults: text
    input/output only, no optional features, and no supported request options.
    """

    lanes: frozenset[AIModelCapabilityLane] = frozenset()
    input_modalities: frozenset[AIModelContentModality] = frozenset({"text"})
    output_modalities: frozenset[AIModelContentModality] = frozenset({"text"})
    supports_tool_calling: bool = False
    tool_choice_modes: frozenset[str] = frozenset()
    supports_reasoning: bool = False
    supports_structured_output: bool = False
    supports_json_mode: bool = False
    supports_streaming: bool = False
    context_window: int | None = None
    output_token_limit: int | None = None
    native_tools: bool = False
    supported_options: frozenset[str] = frozenset()
    specified_fields: frozenset[str] = field(
        default_factory=frozenset,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True)
class AIModelCallOptions:
    """Provider-neutral request options plus required option names."""

    values: dict[str, Any] = field(default_factory=dict)
    required: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AIModelCallRequirements:
    """Runtime requirements for one model call."""

    tool_calling: AIModelToolCallingRequirement = "none"
    streaming: AIModelStreamingRequirement = "none"
    required_modalities: frozenset[AIModelContentModality] = frozenset()
    optional_modalities: frozenset[AIModelContentModality] = frozenset()
    required_options: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AIModelCallDegradation:
    """One deterministic local adjustment made before provider invocation."""

    kind: str
    reason: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIModelCallPlan:
    """Resolved local decision for one provider invocation."""

    action: AIModelCallAction
    selected: Any
    messages: tuple[Any, ...] = ()
    tools: tuple[Any, ...] = ()
    options: dict[str, Any] = field(default_factory=dict)
    capabilities: AIModelCapabilities = field(default_factory=AIModelCapabilities)
    degradations: tuple[AIModelCallDegradation, ...] = ()
    streaming: bool = False
    reason: str | None = None
    diagnostic: str | None = None


class AIModelCapabilityPlanningError(RuntimeError):
    """Raised when local capability planning rejects a provider call."""

    def __init__(self, plan: AIModelCallPlan) -> None:
        self.plan = plan
        diagnostic = plan.diagnostic or plan.reason or "capability unavailable"
        if plan.reason and plan.reason not in diagnostic:
            diagnostic = f"{plan.reason}: {diagnostic}"
        super().__init__(diagnostic)


def json_object_response_format() -> dict[str, Any]:
    """Build a provider-neutral JSON object response-format option."""

    return {"type": "json_object"}


def json_schema_response_format(
    *,
    name: str,
    schema: dict[str, Any],
    strict: bool = True,
) -> dict[str, Any]:
    """Build a provider-neutral JSON schema response-format option."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
            "strict": strict,
        },
    }


def parse_model_capabilities(raw: Any) -> AIModelCapabilities:
    """Parse stored JSON-like capability metadata conservatively."""

    if not isinstance(raw, dict):
        return AIModelCapabilities()

    reasoning = raw.get("reasoning")
    structured_output = raw.get("structured_output")
    native_tools = raw.get("native_tools")
    specified_fields = frozenset(str(key) for key in raw)
    return AIModelCapabilities(
        lanes=_parse_literal_set(raw.get("lanes"), _KNOWN_LANES),
        input_modalities=(
            _parse_literal_set(raw.get("input_modalities"), _KNOWN_MODALITIES)
            or frozenset({"text"})
        ),
        output_modalities=(
            _parse_literal_set(raw.get("output_modalities"), _KNOWN_MODALITIES)
            or frozenset({"text"})
        ),
        supports_tool_calling=_parse_bool(raw.get("tool_calling")),
        tool_choice_modes=_parse_string_set(raw.get("tool_choice_modes")),
        supports_reasoning=(
            _parse_bool(reasoning.get("supported"))
            if isinstance(reasoning, dict)
            else _parse_bool(raw.get("reasoning"))
        ),
        supports_structured_output=(
            _parse_bool(structured_output.get("supported"))
            if isinstance(structured_output, dict)
            else _parse_bool(raw.get("structured_output"))
        ),
        supports_json_mode=_parse_bool(raw.get("json_mode")),
        supports_streaming=_parse_bool(raw.get("streaming")),
        context_window=_parse_positive_int(raw.get("context_window")),
        output_token_limit=_parse_positive_int(raw.get("output_token_limit")),
        native_tools=(
            _parse_bool(native_tools.get("supported"))
            if isinstance(native_tools, dict)
            else _parse_bool(raw.get("native_tools"))
        ),
        supported_options=_parse_string_set(raw.get("supported_options")),
        specified_fields=specified_fields,
    )


def merge_model_capabilities(
    source: AIModelCapabilities,
    model: AIModelCapabilities,
) -> AIModelCapabilities:
    """Overlay source-model capability values on top of source defaults."""

    return replace(
        source,
        lanes=model.lanes if _field_specified(model, "lanes") else source.lanes,
        input_modalities=(
            model.input_modalities
            if _field_specified(model, "input_modalities")
            else source.input_modalities
        ),
        output_modalities=(
            model.output_modalities
            if _field_specified(model, "output_modalities")
            else source.output_modalities
        ),
        supports_tool_calling=(
            model.supports_tool_calling
            if _field_specified(model, "tool_calling")
            else source.supports_tool_calling
        ),
        tool_choice_modes=(
            model.tool_choice_modes
            if _field_specified(model, "tool_choice_modes")
            else source.tool_choice_modes
        ),
        supports_reasoning=(
            model.supports_reasoning
            if _field_specified(model, "reasoning")
            else source.supports_reasoning
        ),
        supports_structured_output=(
            model.supports_structured_output
            if _field_specified(model, "structured_output")
            else source.supports_structured_output
        ),
        supports_json_mode=(
            model.supports_json_mode
            if _field_specified(model, "json_mode")
            else source.supports_json_mode
        ),
        supports_streaming=(
            model.supports_streaming
            if _field_specified(model, "streaming")
            else source.supports_streaming
        ),
        context_window=(
            model.context_window
            if _field_specified(model, "context_window")
            else source.context_window
        ),
        output_token_limit=(
            model.output_token_limit
            if _field_specified(model, "output_token_limit")
            else source.output_token_limit
        ),
        native_tools=(
            model.native_tools
            if _field_specified(model, "native_tools")
            else source.native_tools
        ),
        supported_options=source.supported_options | model.supported_options,
    )


def capabilities_to_metadata(
    capabilities: AIModelCapabilities,
) -> dict[str, Any]:
    """Serialize normalized capability metadata for APIs and diagnostics."""

    return {
        "lanes": sorted(capabilities.lanes),
        "input_modalities": sorted(capabilities.input_modalities),
        "output_modalities": sorted(capabilities.output_modalities),
        "tool_calling": capabilities.supports_tool_calling,
        "tool_choice_modes": sorted(capabilities.tool_choice_modes),
        "reasoning": {"supported": capabilities.supports_reasoning},
        "structured_output": {"supported": capabilities.supports_structured_output},
        "json_mode": capabilities.supports_json_mode,
        "streaming": capabilities.supports_streaming,
        "context_window": capabilities.context_window,
        "output_token_limit": capabilities.output_token_limit,
        "native_tools": {"supported": capabilities.native_tools},
        "supported_options": sorted(capabilities.supported_options),
    }


def _parse_bool(value: Any) -> bool:
    return value is True


def _field_specified(capabilities: AIModelCapabilities, field_name: str) -> bool:
    return field_name in capabilities.specified_fields


def _parse_positive_int(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _parse_literal_set(
    raw: Any,
    allowed: frozenset[str],
) -> frozenset[Any]:
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(item for item in raw if isinstance(item, str) and item in allowed)


def _parse_string_set(raw: Any) -> frozenset[str]:
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(item.strip() for item in raw if isinstance(item, str) and item)
