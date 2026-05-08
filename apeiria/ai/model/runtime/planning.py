"""Local model-call planning before provider invocation."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, TypeAlias

from apeiria.ai.model.runtime.capabilities import (
    AI_MODEL_RESPONSE_FORMAT_OPTION,
    AIModelCallDegradation,
    AIModelCallOptions,
    AIModelCallPlan,
    AIModelCallRequirements,
    AIModelCapabilities,
    AIModelContentModality,
    json_object_response_format,
)

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import (
        AIModelMessage,
        AIModelToolDefinition,
    )

_ResponseFormatPlan: TypeAlias = tuple[
    dict[str, Any] | None,
    tuple[AIModelCallDegradation, ...],
    tuple[str, str] | None,
]


def plan_model_call(  # noqa: C901, PLR0913
    *,
    selected: "AISelectedModel",
    messages: tuple["AIModelMessage", ...] = (),
    tools: tuple["AIModelToolDefinition", ...] = (),
    requirements: AIModelCallRequirements | None = None,
    options: AIModelCallOptions | None = None,
    call_options: dict[str, Any] | None = None,
) -> AIModelCallPlan:
    """Resolve whether and how a selected model may be invoked."""

    requirements = requirements or _infer_requirements(messages=messages, tools=tools)
    effective_options = _merge_options(selected=selected, options=options)
    if call_options:
        effective_options.update(call_options)
    capabilities = _selected_capabilities(selected)
    supported_options = set(capabilities.supported_options)
    requested_required_options = set(requirements.required_options)
    if options is not None:
        requested_required_options.update(options.required)
    response_format_required = (
        AI_MODEL_RESPONSE_FORMAT_OPTION in requested_required_options
    )
    response_format = effective_options.get(AI_MODEL_RESPONSE_FORMAT_OPTION)
    planned_response_format, response_degradations, response_rejection = (
        _plan_response_format(
            response_format,
            capabilities=capabilities,
            required=response_format_required,
        )
    )
    if response_rejection is not None:
        return _reject(
            selected=selected,
            messages=messages,
            tools=tools,
            options=effective_options,
            capabilities=capabilities,
            reason=response_rejection[0],
            diagnostic=response_rejection[1],
        )
    unsupported_required = sorted(
        key
        for key in requested_required_options
        if key != AI_MODEL_RESPONSE_FORMAT_OPTION and key not in supported_options
    )
    if unsupported_required:
        return _reject(
            selected=selected,
            messages=messages,
            tools=tools,
            options=effective_options,
            capabilities=capabilities,
            reason="unsupported_required_option",
            diagnostic=(
                "unsupported required options: " + ", ".join(unsupported_required)
            ),
        )

    streaming_rejection = _plan_streaming_rejection(
        requirements,
        capabilities=capabilities,
    )
    if streaming_rejection is not None:
        return _reject(
            selected=selected,
            messages=messages,
            tools=tools,
            options=effective_options,
            capabilities=capabilities,
            reason=streaming_rejection[0],
            diagnostic=streaming_rejection[1],
        )

    filtered_options = {
        key: value
        for key, value in effective_options.items()
        if key != AI_MODEL_RESPONSE_FORMAT_OPTION and key in supported_options
    }
    if planned_response_format is not None:
        filtered_options[AI_MODEL_RESPONSE_FORMAT_OPTION] = planned_response_format
    if (
        tools
        and requirements.tool_calling == "required"
        and not (capabilities.supports_tool_calling)
    ):
        return _reject(
            selected=selected,
            messages=messages,
            tools=tools,
            options=filtered_options,
            capabilities=capabilities,
            reason="unsupported_tool_calling",
            diagnostic="model does not support required tool calling",
        )

    degradations: list[AIModelCallDegradation] = list(response_degradations)
    streaming, streaming_degradations = _plan_streaming(
        requirements,
        capabilities=capabilities,
    )
    degradations.extend(streaming_degradations)
    planned_tools = tools
    if (
        tools
        and requirements.tool_calling == "optional"
        and not (capabilities.supports_tool_calling)
    ):
        planned_tools = ()
        degradations.append(
            AIModelCallDegradation(
                kind="tools_omitted",
                reason="unsupported_tool_calling",
                detail="model does not support optional tool exposure",
                metadata={"tool_count": len(tools)},
            )
        )

    message_modalities = _message_modalities(messages)
    unsupported_required_modalities = sorted(
        (message_modalities | requirements.required_modalities)
        - capabilities.input_modalities
        - requirements.optional_modalities
    )
    if unsupported_required_modalities:
        return _reject(
            selected=selected,
            messages=messages,
            tools=planned_tools,
            options=filtered_options,
            capabilities=capabilities,
            reason="unsupported_modality",
            diagnostic=(
                "model does not support required modalities: "
                + ", ".join(unsupported_required_modalities)
            ),
        )

    planned_messages = messages
    optional_unsupported = sorted(
        (message_modalities & requirements.optional_modalities)
        - capabilities.input_modalities
    )
    if optional_unsupported:
        planned_messages = _degrade_optional_parts(
            messages,
            optional_unsupported=frozenset(optional_unsupported),
        )
        degradations.append(
            AIModelCallDegradation(
                kind="modalities_replaced",
                reason="unsupported_optional_modality",
                detail=(
                    "unsupported optional modalities replaced: "
                    + ", ".join(optional_unsupported)
                ),
                metadata={"modalities": optional_unsupported},
            )
        )

    return AIModelCallPlan(
        action="invoke",
        selected=selected,
        messages=planned_messages,
        tools=planned_tools,
        options=filtered_options,
        capabilities=capabilities,
        degradations=tuple(degradations),
        streaming=streaming,
    )


def _plan_response_format(
    response_format: Any,
    *,
    capabilities: AIModelCapabilities,
    required: bool,
) -> _ResponseFormatPlan:
    if response_format is None:
        return None, (), None
    if not isinstance(response_format, dict):
        return _handle_invalid_response_format(required=required)

    response_type = response_format.get("type")
    if response_type == "json_schema":
        return _plan_json_schema_response_format(
            response_format,
            capabilities=capabilities,
            required=required,
        )

    if response_type == "json_object":
        return _plan_json_object_response_format(
            response_format,
            capabilities=capabilities,
            required=required,
        )

    return _handle_unsupported_response_format(required=required)


def _plan_json_schema_response_format(
    response_format: dict[str, Any],
    *,
    capabilities: AIModelCapabilities,
    required: bool,
) -> _ResponseFormatPlan:
    if capabilities.supports_structured_output:
        return dict(response_format), (), None
    if capabilities.supports_json_mode:
        return (
            json_object_response_format(),
            (
                AIModelCallDegradation(
                    kind="structured_output_degraded",
                    reason="unsupported_structured_output",
                    detail="JSON schema response format degraded to JSON object mode",
                    metadata={"requested_type": "json_schema"},
                ),
            ),
            None,
        )
    if required:
        return (
            None,
            (),
            (
                "unsupported_structured_output",
                "required response_format is unsupported by selected model",
            ),
        )
    return (
        None,
        (
            _structured_output_omitted(
                "model supports neither JSON schema nor JSON mode"
            ),
        ),
        None,
    )


def _plan_json_object_response_format(
    response_format: dict[str, Any],
    *,
    capabilities: AIModelCapabilities,
    required: bool,
) -> _ResponseFormatPlan:
    if capabilities.supports_json_mode or capabilities.supports_structured_output:
        return dict(response_format), (), None
    if required:
        return (
            None,
            (),
            (
                "unsupported_structured_output",
                "required response_format is unsupported by selected model",
            ),
        )
    return (
        None,
        (_structured_output_omitted("model does not support JSON object mode"),),
        None,
    )


def _handle_invalid_response_format(*, required: bool) -> _ResponseFormatPlan:
    if required:
        return (
            None,
            (),
            (
                "unsupported_structured_output",
                "required response_format is not a valid structured option",
            ),
        )
    return (
        None,
        (_structured_output_omitted("invalid response_format option"),),
        None,
    )


def _handle_unsupported_response_format(*, required: bool) -> _ResponseFormatPlan:
    if required:
        return (
            None,
            (),
            (
                "unsupported_structured_output",
                "required response_format type is unsupported",
            ),
        )
    return (
        None,
        (_structured_output_omitted("unsupported response_format type"),),
        None,
    )


def _structured_output_omitted(detail: str) -> AIModelCallDegradation:
    return AIModelCallDegradation(
        kind="structured_output_omitted",
        reason="unsupported_structured_output",
        detail=detail,
        metadata={"option": AI_MODEL_RESPONSE_FORMAT_OPTION},
    )


def _plan_streaming_rejection(
    requirements: AIModelCallRequirements,
    *,
    capabilities: AIModelCapabilities,
) -> tuple[str, str] | None:
    if requirements.streaming == "required" and not capabilities.supports_streaming:
        return (
            "unsupported_streaming",
            "model does not support required streaming",
        )
    return None


def _plan_streaming(
    requirements: AIModelCallRequirements,
    *,
    capabilities: AIModelCapabilities,
) -> tuple[bool, tuple[AIModelCallDegradation, ...]]:
    if requirements.streaming == "none":
        return False, ()
    if capabilities.supports_streaming:
        return True, ()
    if requirements.streaming == "optional":
        return (
            False,
            (
                AIModelCallDegradation(
                    kind="streaming_omitted",
                    reason="unsupported_streaming",
                    detail="model does not support optional streaming",
                ),
            ),
        )
    return False, ()


def _infer_requirements(
    *,
    messages: tuple["AIModelMessage", ...],
    tools: tuple["AIModelToolDefinition", ...],
) -> AIModelCallRequirements:
    text_modalities: frozenset[AIModelContentModality] = frozenset({"text"})
    modalities = _message_modalities(messages) - text_modalities
    return AIModelCallRequirements(
        tool_calling="required" if tools else "none",
        required_modalities=frozenset(modalities),
    )


def _selected_capabilities(selected: "AISelectedModel") -> AIModelCapabilities:
    capabilities = getattr(selected, "resolved_capabilities", None)
    if isinstance(capabilities, AIModelCapabilities):
        return capabilities
    return AIModelCapabilities()


def _merge_options(
    *,
    selected: "AISelectedModel",
    options: AIModelCallOptions | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    source_defaults = getattr(selected.source, "default_options", None)
    if isinstance(source_defaults, dict):
        merged.update(source_defaults)
    model_defaults = getattr(selected, "model_default_options", None)
    if isinstance(model_defaults, dict):
        merged.update(model_defaults)
    if options is not None:
        merged.update(options.values)
    return merged


def _reject(  # noqa: PLR0913
    *,
    selected: "AISelectedModel",
    messages: tuple["AIModelMessage", ...],
    tools: tuple["AIModelToolDefinition", ...],
    options: dict[str, Any],
    capabilities: AIModelCapabilities,
    reason: str,
    diagnostic: str,
) -> AIModelCallPlan:
    return AIModelCallPlan(
        action="reject",
        selected=selected,
        messages=messages,
        tools=tools,
        options=options,
        capabilities=capabilities,
        reason=reason,
        diagnostic=diagnostic,
    )


def _message_modalities(
    messages: tuple["AIModelMessage", ...],
) -> frozenset[AIModelContentModality]:
    modalities: set[AIModelContentModality] = {"text"}
    for message in messages:
        parts = getattr(message, "parts", ())
        for part in parts:
            modality = getattr(part, "kind", None)
            if modality in {
                "text",
                "image",
                "audio",
                "file",
                "tool_result",
                "provider_data",
            }:
                modalities.add(modality)
    return frozenset(modalities)


def _degrade_optional_parts(
    messages: tuple["AIModelMessage", ...],
    *,
    optional_unsupported: frozenset[str],
) -> tuple["AIModelMessage", ...]:
    degraded: list[AIModelMessage] = []
    for message in messages:
        parts = getattr(message, "parts", ())
        if not parts:
            degraded.append(message)
            continue
        placeholders = [
            f"[{getattr(part, 'kind', 'part')} omitted]"
            for part in parts
            if getattr(part, "kind", None) in optional_unsupported
        ]
        if not placeholders:
            degraded.append(message)
            continue
        degraded.append(
            replace(
                message,
                content=" ".join(
                    item for item in (message.content, *placeholders) if item
                ),
                parts=tuple(
                    part
                    for part in parts
                    if getattr(part, "kind", None) not in optional_unsupported
                ),
            )
        )
    return tuple(degraded)
