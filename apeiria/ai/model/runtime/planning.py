"""Local model-call planning before provider invocation."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model.runtime.capabilities import (
    AIModelCallDegradation,
    AIModelCallOptions,
    AIModelCallPlan,
    AIModelCallRequirements,
    AIModelCapabilities,
    AIModelContentModality,
)

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import (
        AIModelMessage,
        AIModelToolDefinition,
    )


def plan_model_call(  # noqa: PLR0913
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
    unsupported_required = sorted(
        key for key in requested_required_options if key not in supported_options
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

    filtered_options = {
        key: value
        for key, value in effective_options.items()
        if key in supported_options
    }
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

    degradations: list[AIModelCallDegradation] = []
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
    )


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
