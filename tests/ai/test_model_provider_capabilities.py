from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from pytest import raises

from apeiria.ai.model.adapters import openai_compatible
from apeiria.ai.model.catalog.capability_templates import (
    ModelCapabilityTemplate,
    ModelCapabilityTemplateRegistry,
    enrich_model_capabilities,
    model_capability_template_registry,
)
from apeiria.ai.model.catalog.models import AIChatModelDefinition
from apeiria.ai.model.routing.models import AIModelProfileDefinition
from apeiria.ai.model.routing.selection import (
    AISelectedModel,
    resolve_source_selected_model_with_fallback,
)
from apeiria.ai.model.runtime.adapter import (
    AIModelContentPart,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelMessage,
    AIModelToolDefinition,
)
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallOptions,
    AIModelCallRequirements,
    AIModelCapabilities,
    AIModelCapabilityPlanningError,
    merge_model_capabilities,
    parse_model_capabilities,
)
from apeiria.ai.model.runtime.capability_sources import (
    CapabilityFactLayer,
    CapabilityFactProvenance,
    capability_provenance_to_metadata,
    classify_capability_mismatch,
    mark_owner_overrides,
    merge_capability_fact_layers,
    parse_capability_provenance,
)
from apeiria.ai.model.runtime.factory import (
    UnsupportedAIModelAdapterKindError,
    build_source_adapter,
)
from apeiria.ai.model.runtime.planning import plan_model_call
from apeiria.ai.model.runtime.registry import provider_adapter_registry
from apeiria.ai.model.sources.models import (
    SOURCE_PRESETS,
    AISourceDefinition,
    resolve_adapter_kind_for_client_type,
)
from tests.ai.agent_turn_helpers import ModelInvokerStub, model_response

_TEST_TEMPERATURE = 0.2


def test_provider_protocol_registry_resolves_current_adapter_kinds() -> None:
    entries = provider_adapter_registry.list_entries()

    assert {entry.adapter_kind for entry in entries} >= {
        "openai_compatible",
        "anthropic_compatible",
        "generic_rerank",
    }
    assert (
        provider_adapter_registry.get("openai_compatible").operation_support.chat
        is True
    )
    assert (
        provider_adapter_registry.get("generic_rerank").operation_support.rerank is True
    )
    with raises(UnsupportedAIModelAdapterKindError):
        provider_adapter_registry.get("missing-provider")


def test_runtime_adapter_selection_uses_adapter_kind_not_preset() -> None:
    source = AISourceDefinition(
        source_id="source-template",
        name="Template Mismatch",
        capability_type="chat_completion",
        client_type="anthropic",
        preset_type="anthropic_compatible",
        api_base="https://api.example.test/v1",
        adapter_kind="openai_compatible",
    )

    adapter = build_source_adapter(source, api_key="test-key")

    assert adapter.__class__.__name__ == "OpenAICompatibleProvider"
    assert any(
        preset.preset_type == "anthropic_compatible"
        and preset.adapter_kind == "anthropic_compatible"
        for preset in SOURCE_PRESETS
    )
    assert any(
        preset.preset_type == "openrouter"
        and preset.adapter_kind == "openai_compatible"
        and preset.default_api_base == "https://openrouter.ai/api/v1"
        for preset in SOURCE_PRESETS
    )
    assert resolve_adapter_kind_for_client_type("openai") == "openai_compatible"


def test_model_capabilities_parse_defaults_and_model_overrides() -> None:
    conservative = parse_model_capabilities(None)
    source = parse_model_capabilities(
        {
            "lanes": ["chat_completion"],
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
            "tool_calling": True,
            "supported_options": ["temperature"],
            "unknown_field": "ignored",
        }
    )
    model = parse_model_capabilities(
        {
            "input_modalities": ["text"],
            "reasoning": {"supported": True},
            "supported_options": ["max_tokens"],
        }
    )
    merged = merge_model_capabilities(source, model)

    assert conservative.input_modalities == frozenset({"text"})
    assert conservative.supports_tool_calling is False
    assert source.supports_tool_calling is True
    assert merged.input_modalities == frozenset({"text"})
    assert merged.supports_tool_calling is True
    assert merged.supports_reasoning is True
    assert merged.supported_options == frozenset({"temperature", "max_tokens"})


def test_capability_provenance_parses_and_serializes_safely() -> None:
    parsed = parse_capability_provenance(
        {
            "capability.tool_calling": {
                "source": "model_template",
                "confidence": "inferred",
                "detail": "matched gpt-4o*",
                "updated_at": "2026-04-29T00:00:00+00:00",
                "unexpected": "ignored",
            },
            "broken": {"source": "not-real"},
        }
    )

    serialized = capability_provenance_to_metadata(parsed)

    assert parsed == {
        "capability.tool_calling": CapabilityFactProvenance(
            source="model_template",
            confidence="inferred",
            detail="matched gpt-4o*",
            updated_at="2026-04-29T00:00:00+00:00",
        )
    }
    assert serialized == {
        "capability.tool_calling": {
            "source": "model_template",
            "confidence": "inferred",
            "detail": "matched gpt-4o*",
            "updated_at": "2026-04-29T00:00:00+00:00",
        }
    }
    assert parse_capability_provenance(None) == {}


def test_capability_fact_layers_merge_with_fixed_precedence() -> None:
    merged = merge_capability_fact_layers(
        CapabilityFactLayer(
            source="adapter_default",
            confidence="default",
            capability_metadata={
                "tool_calling": True,
                "supported_options": ["temperature"],
            },
            default_options={"temperature": 0.7},
            detail="adapter family",
        ),
        CapabilityFactLayer(
            source="model_template",
            confidence="inferred",
            capability_metadata={
                "tool_calling": False,
                "supported_options": ["max_tokens"],
            },
            default_options={"max_tokens": 128},
            detail="unknown model is conservative",
        ),
        CapabilityFactLayer(
            source="upstream_catalog",
            confidence="reported",
            capability_metadata={"streaming": True},
            detail="provider catalog",
        ),
        CapabilityFactLayer(
            source="owner_override",
            confidence="owner",
            capability_metadata={"tool_calling": True},
            default_options={"temperature": 0.2},
            detail="manual edit",
        ),
        CapabilityFactLayer(
            source="runtime_observation",
            confidence="reported",
            capability_metadata={"tool_calling": False},
            detail="provider rejected tools",
        ),
    )

    assert merged.capability_metadata == {
        "streaming": True,
        "supported_options": ["temperature", "max_tokens"],
        "tool_calling": True,
    }
    assert merged.default_options == {"temperature": 0.2, "max_tokens": 128}
    assert merged.provenance["capability.tool_calling"].source == "owner_override"
    assert merged.provenance["capability.streaming"].source == "upstream_catalog"
    assert merged.provenance["option.temperature"].source == "owner_override"
    assert all(
        item.source != "runtime_observation" for item in merged.provenance.values()
    )


def test_owner_override_marks_only_supplied_fields() -> None:
    provenance = mark_owner_overrides(
        capability_metadata={"tool_calling": False},
        default_options={"temperature": 0.1},
        existing=parse_capability_provenance(
            {
                "capability.streaming": {
                    "source": "upstream_catalog",
                    "confidence": "reported",
                }
            }
        ),
    )

    assert provenance["capability.tool_calling"].source == "owner_override"
    assert provenance["option.temperature"].source == "owner_override"
    assert provenance["capability.streaming"].source == "upstream_catalog"
    assert "capability.reasoning" not in provenance


def test_model_capability_template_registry_matches_deterministically() -> None:
    registry = ModelCapabilityTemplateRegistry(
        (
            ModelCapabilityTemplate(
                template_id="low-glob",
                adapter_kind="openai_compatible",
                identifier_patterns=("gpt-4o*",),
                priority=10,
                capability_metadata={"tool_calling": False},
            ),
            ModelCapabilityTemplate(
                template_id="high-exact",
                adapter_kind="openai_compatible",
                identifier_patterns=("gpt-4o-mini",),
                priority=20,
                capability_metadata={"tool_calling": True},
            ),
            ModelCapabilityTemplate(
                template_id="other-adapter",
                adapter_kind="anthropic_compatible",
                identifier_patterns=("gpt-4o-mini",),
                priority=99,
                capability_metadata={"tool_calling": False},
            ),
        )
    )

    matched = registry.select(
        adapter_kind="openai_compatible",
        model_identifier="GPT-4O-MINI",
        source_hints=(),
    )

    assert matched is not None
    assert matched.template_id == "high-exact"
    assert (
        registry.select(
            adapter_kind="openai_compatible",
            model_identifier="unknown-model",
            source_hints=(),
        )
        is None
    )


def test_default_capability_template_enrichment_is_model_specific() -> None:
    known = enrich_model_capabilities(
        source=_source("source-openai"),
        model_identifier="gpt-4o-mini",
        registry=model_capability_template_registry,
    )
    unknown = enrich_model_capabilities(
        source=_source("source-openai"),
        model_identifier="unknown-openai-compatible-model",
        registry=model_capability_template_registry,
    )

    assert known.capability_metadata["tool_calling"] is True
    assert "image" in known.capability_metadata["input_modalities"]
    assert known.provenance["capability.tool_calling"].source == "model_template"
    assert unknown.capability_metadata["tool_calling"] is False
    assert unknown.provenance["capability.tool_calling"].source == "preset_template"


def test_selected_model_preserves_source_model_metadata() -> None:
    source = _source("source-primary")
    fallback_source = _source("source-fallback")
    primary_model = AIChatModelDefinition(
        model_id="model-primary",
        source_id=source.source_id,
        model_identifier="gpt-primary",
        display_name="Primary",
        extra_params={"temperature": 0.2},
        default_options={"max_tokens": 100},
        capability_metadata={"tool_calling": False},
    )
    fallback_model = AIChatModelDefinition(
        model_id="model-fallback",
        source_id=fallback_source.source_id,
        model_identifier="gpt-fallback",
        display_name="Fallback",
        extra_params={"temperature": 0.1},
        default_options={"max_tokens": 200},
        capability_metadata={"tool_calling": True},
    )
    primary = _profile("profile-primary", primary_model.model_id, "profile-fallback")
    fallback = _profile("profile-fallback", fallback_model.model_id, None)

    selected = resolve_source_selected_model_with_fallback(
        [source, fallback_source],
        [primary_model, fallback_model],
        [primary, fallback],
        [primary],
    )

    assert selected is not None
    assert selected.source_model == primary_model
    assert selected.model_default_options == {"max_tokens": 100}
    assert selected.resolved_capabilities.supports_tool_calling is False

    fallback_only = resolve_source_selected_model_with_fallback(
        [fallback_source],
        [primary_model, fallback_model],
        [primary, fallback],
        [primary],
    )

    assert fallback_only is not None
    assert fallback_only.source_model == fallback_model
    assert fallback_only.model_default_options == {"max_tokens": 200}
    assert fallback_only.resolved_capabilities.supports_tool_calling is True


def test_selected_model_skips_disabled_primary_model() -> None:
    source = _source("source-primary")
    fallback_source = _source("source-fallback")
    disabled_primary_model = AIChatModelDefinition(
        model_id="model-primary",
        source_id=source.source_id,
        model_identifier="gpt-primary",
        display_name="Primary",
        enabled=False,
        capability_metadata={"tool_calling": False},
    )
    fallback_model = AIChatModelDefinition(
        model_id="model-fallback",
        source_id=fallback_source.source_id,
        model_identifier="gpt-fallback",
        display_name="Fallback",
        capability_metadata={"tool_calling": True},
    )
    primary = _profile(
        "profile-primary",
        disabled_primary_model.model_id,
        "profile-fallback",
    )
    fallback = _profile("profile-fallback", fallback_model.model_id, None)

    selected = resolve_source_selected_model_with_fallback(
        [source, fallback_source],
        [disabled_primary_model, fallback_model],
        [primary, fallback],
        [primary],
    )

    assert selected is not None
    assert selected.source_model == fallback_model
    assert selected.resolved_model_name == "gpt-fallback"
    assert selected.resolved_capabilities.supports_tool_calling is True


def test_model_call_planning_invokes_rejects_degrades_and_filters_options() -> None:
    selected = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=False,
            supported_options=frozenset({"temperature"}),
        )
    )
    tools = (
        AIModelToolDefinition(
            name="memory_query",
            description="Query memory",
            parameters={"type": "object"},
        ),
    )

    rejected = plan_model_call(
        selected=selected,
        messages=(AIModelMessage(role="user", content="hello"),),
        tools=tools,
        requirements=AIModelCallRequirements(tool_calling="required"),
    )
    degraded = plan_model_call(
        selected=selected,
        messages=(AIModelMessage(role="user", content="hello"),),
        tools=tools,
        requirements=AIModelCallRequirements(tool_calling="optional"),
        options=AIModelCallOptions(values={"temperature": 0.2, "seed": 1}),
    )
    multimodal = plan_model_call(
        selected=selected,
        messages=(
            AIModelMessage(
                role="user",
                content="see image",
                parts=(
                    AIModelContentPart(kind="text", text="see image"),
                    AIModelContentPart.image(url="https://example.test/image.png"),
                ),
            ),
        ),
        requirements=AIModelCallRequirements(optional_modalities=frozenset({"image"})),
    )
    required_multimodal = plan_model_call(
        selected=selected,
        messages=(
            AIModelMessage(
                role="user",
                content="see image",
                parts=(
                    AIModelContentPart(kind="text", text="see image"),
                    AIModelContentPart.image(url="https://example.test/image.png"),
                ),
            ),
        ),
        requirements=AIModelCallRequirements(required_modalities=frozenset({"image"})),
    )

    assert rejected.action == "reject"
    assert rejected.reason == "unsupported_tool_calling"
    assert degraded.action == "invoke"
    assert degraded.tools == ()
    assert degraded.options == {"temperature": 0.2}
    assert degraded.degradations[0].kind == "tools_omitted"
    assert multimodal.action == "invoke"
    assert multimodal.messages[0].content.endswith("[image omitted]")
    assert required_multimodal.action == "reject"
    assert required_multimodal.reason == "unsupported_modality"


def test_model_call_planning_keeps_structured_schema_when_supported() -> None:
    selected = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_structured_output=True,
            supported_options=frozenset({"temperature"}),
        )
    )
    response_format = _json_schema_response_format()

    plan = plan_model_call(
        selected=selected,
        options=AIModelCallOptions(
            values={
                "response_format": response_format,
                "temperature": _TEST_TEMPERATURE,
            }
        ),
    )

    assert plan.action == "invoke"
    assert plan.options["response_format"] == response_format
    assert plan.options["temperature"] == _TEST_TEMPERATURE
    assert plan.degradations == ()


def test_model_call_planning_degrades_optional_schema_to_json_object() -> None:
    selected = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_json_mode=True,
        )
    )

    plan = plan_model_call(
        selected=selected,
        options=AIModelCallOptions(
            values={"response_format": _json_schema_response_format()}
        ),
    )

    assert plan.action == "invoke"
    assert plan.options["response_format"] == {"type": "json_object"}
    assert plan.degradations[0].kind == "structured_output_degraded"
    assert plan.degradations[0].reason == "unsupported_structured_output"


def test_model_call_planning_omits_optional_response_format() -> None:
    selected = _selected_with_capabilities(AIModelCapabilities())

    plan = plan_model_call(
        selected=selected,
        options=AIModelCallOptions(
            values={"response_format": _json_schema_response_format()}
        ),
    )

    assert plan.action == "invoke"
    assert "response_format" not in plan.options
    assert plan.degradations[0].kind == "structured_output_omitted"
    assert plan.degradations[0].reason == "unsupported_structured_output"


def test_model_call_planning_rejects_required_response_format() -> None:
    selected = _selected_with_capabilities(AIModelCapabilities())

    plan = plan_model_call(
        selected=selected,
        options=AIModelCallOptions(
            values={"response_format": _json_schema_response_format()},
            required=frozenset({"response_format"}),
        ),
    )

    assert plan.action == "reject"
    assert plan.reason == "unsupported_structured_output"
    assert "response_format" in (plan.diagnostic or "")


def test_openai_compatible_adapter_forwards_json_object_response_format(
    monkeypatch: Any,
) -> None:
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(
        openai_compatible,
        "_build_openai_client",
        lambda **_kwargs: _OpenAIClientStub(payloads),
    )
    provider = openai_compatible.OpenAICompatibleProvider(
        api_base="https://api.example.test/v1",
        api_key="test-key",
    )

    asyncio.run(
        provider.generate_text(
            AIModelGenerateRequest(
                source_id="source-1",
                model_name="model-1",
                messages=(AIModelMessage(role="user", content="hello"),),
                options={"response_format": {"type": "json_object"}},
            )
        )
    )

    assert payloads[0]["response_format"] == {"type": "json_object"}


def test_openai_compatible_adapter_forwards_json_schema_response_format(
    monkeypatch: Any,
) -> None:
    payloads: list[dict[str, Any]] = []
    response_format = _json_schema_response_format()
    monkeypatch.setattr(
        openai_compatible,
        "_build_openai_client",
        lambda **_kwargs: _OpenAIClientStub(payloads),
    )
    provider = openai_compatible.OpenAICompatibleProvider(
        api_base="https://api.example.test/v1",
        api_key="test-key",
    )

    asyncio.run(
        provider.generate_text(
            AIModelGenerateRequest(
                source_id="source-1",
                model_name="model-1",
                messages=(AIModelMessage(role="user", content="hello"),),
                options={"response_format": response_format},
            )
        )
    )

    assert payloads[0]["response_format"] == response_format


def test_agent_runtime_uses_fallback_after_capability_planning_reject() -> None:
    from apeiria.app.ai.agent_turn import (
        AgentModelGenerationRequest,
        AgentTurnModelRuntime,
    )

    primary = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=False,
        ),
        suffix="primary",
        fallback_profile_id="profile-fallback",
    )
    fallback = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=True,
        ),
        suffix="fallback",
    )
    invoker = ModelInvokerStub(
        [
            AIModelCapabilityPlanningError(
                plan_model_call(
                    selected=primary,
                    tools=(
                        AIModelToolDefinition(
                            name="memory_query",
                            description="Query memory",
                            parameters={"type": "object"},
                        ),
                    ),
                    requirements=AIModelCallRequirements(tool_calling="required"),
                )
            ),
            model_response(fallback, "fallback answer"),
        ]
    )
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-capability",
                session_id="session-1",
                runtime_mode="message",
                selected=primary,
                prompt="use tools",
                tools=(
                    AIModelToolDefinition(
                        name="memory_query",
                        description="Query memory",
                        parameters={"type": "object"},
                    ),
                ),
                fallback_models=(fallback,),
            )
        )
    )

    assert result.response is not None
    assert result.response.content == "fallback answer"
    assert result.turn.model_attempts[0].reason == "capability_unavailable"
    assert "unsupported_tool_calling" in (
        result.turn.model_attempts[0].diagnostic or ""
    )
    assert result.turn.model_attempts[1].status == "success"


def test_runtime_records_capability_mismatch_observation_with_fallback() -> None:
    from apeiria.app.ai.agent_turn import (
        AgentModelGenerationRequest,
        AgentTurnModelRuntime,
    )

    primary = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=True,
        ),
        suffix="primary",
        fallback_profile_id="profile-fallback",
    )
    fallback = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=True,
        ),
        suffix="fallback",
    )
    invoker = ModelInvokerStub(
        [
            RuntimeError(
                "tool calls are not supported for this model api_key=secret-token"
            ),
            model_response(fallback, "fallback answer"),
        ]
    )
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-mismatch",
                session_id="session-1",
                runtime_mode="message",
                selected=primary,
                prompt="use tools",
                tools=(
                    AIModelToolDefinition(
                        name="memory_query",
                        description="Query memory",
                        parameters={"type": "object"},
                    ),
                ),
                fallback_models=(fallback,),
            )
        )
    )

    observation = result.turn.model_attempts[0].capability_observation
    assert result.response is not None
    assert result.turn.model_attempts[0].reason == "capability_unavailable"
    assert observation is not None
    assert observation.planned_feature == "tool_calling"
    assert observation.model_ref == "source-primary:model-primary"
    assert "secret-token" not in observation.diagnostic
    assert result.turn.model_attempts[1].status == "success"
    assert invoker.calls == [primary, fallback]


def test_capability_mismatch_classifier_recognizes_bounded_errors() -> None:
    observation = classify_capability_mismatch(
        RuntimeError("response_format is unsupported by this model"),
        planned_feature="structured_output",
        model_ref="source:model",
    )

    assert observation is not None
    assert observation.planned_feature == "structured_output"
    assert observation.model_ref == "source:model"
    assert observation.suggested_correction == "review model capability metadata"


def test_text_message_and_rich_response_contract_remain_compatible() -> None:
    from apeiria.ai.turn_records import is_empty_model_response

    message = AIModelMessage(role="user", content="plain text")
    response = AIModelGenerateResponse(
        source_id="source-1",
        model_name="model-1",
        content="hello",
        parts=(AIModelContentPart(kind="text", text="hello"),),
        usage={"input_tokens": 2, "output_tokens": 1},
        finish_reason="stop",
        response_id="resp-1",
        reasoning_content="short reasoning",
        reasoning_signature="sig-1",
        provider_data={"continuation": "next"},
        raw={"id": "resp-1"},
    )

    request = AIModelGenerateRequest(
        source_id="source-1",
        model_name="model-1",
        messages=(message,),
    )

    assert request.messages[0].content == "plain text"
    assert request.messages[0].text_content == "plain text"
    assert response.content == "hello"
    assert response.text_content == "hello"
    assert response.usage == {"input_tokens": 2, "output_tokens": 1}
    assert (
        is_empty_model_response(
            AIModelGenerateResponse(
                source_id="source-1",
                model_name="model-1",
                content="",
                parts=(AIModelContentPart(kind="text", text="part text"),),
            )
        )
        is False
    )


def _source(source_id: str) -> AISourceDefinition:
    return AISourceDefinition(
        source_id=source_id,
        name=source_id,
        capability_type="chat_completion",
        client_type="openai",
        preset_type="openai_compatible",
        api_base="https://api.example.test/v1",
    )


def _profile(
    profile_id: str,
    model_id: str,
    fallback_profile_id: str | None,
) -> AIModelProfileDefinition:
    return AIModelProfileDefinition(
        profile_id=profile_id,
        name=profile_id,
        model_id=model_id,
        task_class="reply_default",
        priority=10,
        enabled=True,
        fallback_profile_id=fallback_profile_id,
    )


def _selected_with_capabilities(
    capabilities: AIModelCapabilities,
    *,
    suffix: str = "main",
    fallback_profile_id: str | None = None,
) -> AISelectedModel:
    source_model = AIChatModelDefinition(
        model_id=f"model-{suffix}",
        source_id=f"source-{suffix}",
        model_identifier=f"model-{suffix}",
        display_name=f"Model {suffix}",
    )
    return AISelectedModel(
        source=_source(f"source-{suffix}"),
        source_model=source_model,
        profile=_profile(
            f"profile-{suffix}",
            source_model.model_id,
            fallback_profile_id,
        ),
        resolved_model_name=source_model.model_identifier,
        resolved_capabilities=capabilities,
    )


def _json_schema_response_format() -> dict[str, Any]:
    from apeiria.ai.model.runtime import capabilities as capability_contracts

    factory = getattr(capability_contracts, "json_schema_response_format", None)
    assert factory is not None
    return factory(
        name="test_schema",
        schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    )


class _OpenAIClientStub:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create_completion)
        )
        self._payloads = payloads

    async def _create_completion(self, **payload: Any) -> Any:
        self._payloads.append(payload)

        def model_dump(**_kwargs: Any) -> dict[str, Any]:
            return {
                "id": "resp-1",
                "usage": {"prompt_tokens": 1},
            }

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok":true}', tool_calls=[]),
                    finish_reason="stop",
                )
            ],
            model_dump=model_dump,
        )

    async def close(self) -> None:
        return None
