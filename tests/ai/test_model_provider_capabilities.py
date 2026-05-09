from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from pytest import raises

from apeiria.ai.model.adapters import (
    anthropic_compatible,
    gemini_native,
    ollama_native,
    openai_compatible,
)
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
    AIModelSpeechResponse,
    AIModelStreamEvent,
    AIModelStreamRequest,
    AIModelToolDefinition,
    AIModelTranscriptionResponse,
)
from apeiria.ai.model.runtime.capabilities import (
    AI_MODEL_REASONING_EFFORT_OPTION,
    AIModelCallOptions,
    AIModelCallRequirements,
    AIModelCapabilities,
    AIModelCapabilityPlanningError,
    merge_model_capabilities,
    normalize_reasoning_effort,
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
from apeiria.ai.model.runtime.normalization import sanitize_visible_reasoning
from apeiria.ai.model.runtime.planning import plan_model_call
from apeiria.ai.model.runtime.registry import provider_adapter_registry
from apeiria.ai.model.sources.models import (
    SOURCE_PRESETS,
    AISourceDefinition,
    resolve_adapter_kind_for_client_type,
)
from tests.ai.agent_turn_helpers import ModelInvokerStub, model_response

_TEST_TEMPERATURE = 0.2
_TEST_MAX_TOKENS = 32
_HTTP_BAD_REQUEST = 400


def test_provider_protocol_registry_resolves_current_adapter_kinds() -> None:
    entries = provider_adapter_registry.list_entries()

    assert {entry.adapter_kind for entry in entries} >= {
        "openai_compatible",
        "anthropic_compatible",
        "generic_rerank",
        "gemini_native",
        "ollama_native",
    }
    assert (
        provider_adapter_registry.get("openai_compatible").operation_support.chat
        is True
    )
    assert (
        provider_adapter_registry.get("generic_rerank").operation_support.rerank is True
    )
    assert provider_adapter_registry.get("gemini_native").operation_support.chat is True
    assert (
        provider_adapter_registry.get("gemini_native").operation_support.embedding
        is True
    )
    assert provider_adapter_registry.get("ollama_native").operation_support.chat is True
    assert (
        provider_adapter_registry.get("ollama_native").operation_support.embedding
        is True
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
    assert "openrouter" not in {preset.preset_type for preset in SOURCE_PRESETS}
    assert resolve_adapter_kind_for_client_type("openai") == "openai_compatible"
    assert resolve_adapter_kind_for_client_type("gemini") == "gemini_native"
    assert resolve_adapter_kind_for_client_type("ollama") == "ollama_native"


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
            "reasoning": {"supported": True, "efforts": ["low", "medium"]},
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
    assert merged.reasoning_efforts == frozenset({"low", "medium"})
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


def test_default_capability_template_registry_is_empty_and_conservative() -> None:
    assert (
        model_capability_template_registry.select(
            adapter_kind="openai_compatible",
            model_identifier="gpt-4o-mini",
            source_hints=(),
        )
        is None
    )
    assert (
        model_capability_template_registry.select(
            adapter_kind="anthropic_compatible",
            model_identifier="claude-3-5-sonnet",
            source_hints=(),
        )
        is None
    )

    known_name = enrich_model_capabilities(
        source=_source("source-openai"),
        model_identifier="gpt-4o-mini",
        registry=model_capability_template_registry,
    )
    unknown = enrich_model_capabilities(
        source=_source("source-openai"),
        model_identifier="unknown-openai-compatible-model",
        registry=model_capability_template_registry,
    )

    assert known_name.capability_metadata["tool_calling"] is False
    assert known_name.capability_metadata["input_modalities"] == ["text"]
    assert known_name.provenance["capability.tool_calling"].source == "preset_template"
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


def test_speech_model_call_planning_validates_lanes_inputs_and_options() -> None:
    stt = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"speech_to_text"}),
            input_modalities=frozenset({"audio"}),
            output_modalities=frozenset({"text"}),
            supported_options=frozenset({"language"}),
        ),
        suffix="stt",
    )
    tts = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"text_to_speech"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"audio"}),
            supported_options=frozenset({"voice", "response_format"}),
        ),
        suffix="tts",
    )
    chat = _selected_with_capabilities(
        AIModelCapabilities(lanes=frozenset({"chat_completion"})),
        suffix="chat",
    )

    stt_plan = plan_model_call(
        selected=stt,
        requirements=AIModelCallRequirements(
            required_lanes=frozenset({"speech_to_text"}),
            required_modalities=frozenset({"audio"}),
            required_output_modalities=frozenset({"text"}),
        ),
        options=AIModelCallOptions(values={"language": "en", "voice": "alloy"}),
    )
    tts_plan = plan_model_call(
        selected=tts,
        requirements=AIModelCallRequirements(
            required_lanes=frozenset({"text_to_speech"}),
            required_modalities=frozenset({"text"}),
            required_output_modalities=frozenset({"audio"}),
            required_options=frozenset({"voice"}),
        ),
        options=AIModelCallOptions(
            values={"voice": "verse", "response_format": "mp3", "seed": 1}
        ),
    )
    rejected = plan_model_call(
        selected=chat,
        requirements=AIModelCallRequirements(
            required_lanes=frozenset({"speech_to_text"}),
            required_modalities=frozenset({"audio"}),
            required_output_modalities=frozenset({"text"}),
        ),
    )

    assert stt_plan.action == "invoke"
    assert stt_plan.options == {"language": "en"}
    assert tts_plan.action == "invoke"
    assert tts_plan.options == {"voice": "verse", "response_format": "mp3"}
    assert rejected.action == "reject"
    assert rejected.reason == "unsupported_capability_lane"


def test_model_invoker_plans_stt_and_tts_before_provider_invocation(
    monkeypatch: Any,
) -> None:
    from apeiria.ai.model.runtime import service as service_module

    stt_model = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"speech_to_text"}),
            input_modalities=frozenset({"audio"}),
            output_modalities=frozenset({"text"}),
            supported_options=frozenset({"language"}),
        ),
        suffix="stt",
    )
    tts_model = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"text_to_speech"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"audio"}),
            supported_options=frozenset({"voice", "response_format"}),
        ),
        suffix="tts",
    )
    unsupported = _selected_with_capabilities(
        AIModelCapabilities(lanes=frozenset({"chat_completion"})),
        suffix="unsupported",
    )
    client = _SpeechClientStub()
    monkeypatch.setattr(
        service_module.ai_source_service,
        "get_source_api_key",
        lambda _source: "test-key",
    )
    monkeypatch.setattr(service_module, "ai_model_client", client)
    monkeypatch.setattr(
        service_module.ModelInvoker,
        "_register_source",
        staticmethod(lambda *_args, **_kwargs: None),
    )
    invoker = service_module.ModelInvoker()

    transcription = asyncio.run(
        invoker.transcribe_audio(
            stt_model,
            audio_bytes=b"audio",
            file_name="voice.ogg",
            mime_type="audio/ogg",
            language="en",
        )
    )
    speech = asyncio.run(
        invoker.synthesize_speech(
            tts_model,
            text="hello",
            voice="verse",
            response_format="mp3",
        )
    )
    with raises(AIModelCapabilityPlanningError):
        asyncio.run(invoker.transcribe_audio(unsupported, audio_bytes=b"audio"))
    with raises(AIModelCapabilityPlanningError):
        asyncio.run(
            invoker.synthesize_speech(
                _selected_with_capabilities(
                    AIModelCapabilities(
                        lanes=frozenset({"text_to_speech"}),
                        input_modalities=frozenset({"text"}),
                        output_modalities=frozenset({"audio"}),
                    ),
                    suffix="no-voice",
                ),
                text="hello",
                voice="verse",
            )
        )

    assert transcription.text == "transcribed"
    assert speech.response_format == "mp3"
    assert client.transcription_requests[0].source_id == stt_model.source.source_id
    assert client.transcription_requests[0].model_name == "model-stt"
    assert client.transcription_requests[0].language == "en"
    assert client.speech_requests[0].source_id == tts_model.source.source_id
    assert client.speech_requests[0].model_name == "model-tts"
    assert client.speech_requests[0].voice == "verse"
    assert client.speech_requests[0].response_format == "mp3"
    assert client.transcription_requests[1:] == []
    assert client.speech_requests[1:] == []


def test_streaming_generation_events_are_provider_neutral_contracts() -> None:
    selected = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_streaming=True,
        )
    )
    request = AIModelStreamRequest(
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or "",
        messages=(AIModelMessage(role="user", content="hello"),),
    )
    final_response = AIModelGenerateResponse(
        source_id=request.source_id,
        model_name=request.model_name,
        content="hello there",
        usage={"completion_tokens": 2},
        finish_reason="stop",
        response_id="resp-1",
    )

    events = (
        AIModelStreamEvent.start(
            source_id=request.source_id,
            model_name=request.model_name,
            stream_id="stream-1",
        ),
        AIModelStreamEvent.text_delta(
            source_id=request.source_id,
            model_name=request.model_name,
            stream_id="stream-1",
            content_delta="hello",
        ),
        AIModelStreamEvent.final(
            source_id=request.source_id,
            model_name=request.model_name,
            stream_id="stream-1",
            response=final_response,
        ),
        AIModelStreamEvent.failure(
            source_id=request.source_id,
            model_name=request.model_name,
            stream_id="stream-2",
            reason="upstream_error",
            diagnostic="provider stream failed",
        ),
    )

    assert [event.kind for event in events] == [
        "start",
        "text_delta",
        "final",
        "failure",
    ]
    assert events[1].content_delta == "hello"
    assert events[2].response == final_response
    assert events[3].reason == "upstream_error"
    assert events[3].diagnostic == "provider stream failed"
    assert not any(hasattr(event, "raw") for event in events)


def test_model_call_planning_handles_required_and_optional_streaming() -> None:
    unsupported = _selected_with_capabilities(
        AIModelCapabilities(lanes=frozenset({"chat_completion"})),
        suffix="no-stream",
    )
    supported = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_streaming=True,
        ),
        suffix="stream",
    )

    rejected = plan_model_call(
        selected=unsupported,
        requirements=AIModelCallRequirements(streaming="required"),
    )
    degraded = plan_model_call(
        selected=unsupported,
        requirements=AIModelCallRequirements(streaming="optional"),
    )
    planned = plan_model_call(
        selected=supported,
        requirements=AIModelCallRequirements(streaming="optional"),
    )

    assert rejected.action == "reject"
    assert rejected.reason == "unsupported_streaming"
    assert degraded.action == "invoke"
    assert degraded.streaming is False
    assert degraded.degradations[0].kind == "streaming_omitted"
    assert planned.action == "invoke"
    assert planned.streaming is True
    assert planned.degradations == ()


def test_model_call_planning_handles_reasoning_effort_options() -> None:
    unsupported = _selected_with_capabilities(
        AIModelCapabilities(lanes=frozenset({"chat_completion"})),
        suffix="no-reasoning",
    )
    supported = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_reasoning=True,
            supported_options=frozenset({AI_MODEL_REASONING_EFFORT_OPTION}),
        ),
        suffix="reasoning",
    )

    planned = plan_model_call(
        selected=supported,
        options=AIModelCallOptions(values={AI_MODEL_REASONING_EFFORT_OPTION: "medium"}),
    )
    degraded = plan_model_call(
        selected=unsupported,
        options=AIModelCallOptions(values={AI_MODEL_REASONING_EFFORT_OPTION: "high"}),
    )
    rejected = plan_model_call(
        selected=unsupported,
        options=AIModelCallOptions(
            values={AI_MODEL_REASONING_EFFORT_OPTION: "low"},
            required=frozenset({AI_MODEL_REASONING_EFFORT_OPTION}),
        ),
    )
    invalid = plan_model_call(
        selected=supported,
        options=AIModelCallOptions(
            values={AI_MODEL_REASONING_EFFORT_OPTION: "extreme"}
        ),
    )

    assert normalize_reasoning_effort("low") == "low"
    assert normalize_reasoning_effort("medium") == "medium"
    assert normalize_reasoning_effort("high") == "high"
    assert normalize_reasoning_effort("extreme") is None
    assert planned.action == "invoke"
    assert planned.options[AI_MODEL_REASONING_EFFORT_OPTION] == "medium"
    assert planned.degradations == ()
    assert degraded.action == "invoke"
    assert AI_MODEL_REASONING_EFFORT_OPTION not in degraded.options
    assert degraded.degradations[0].kind == "reasoning_omitted"
    assert degraded.degradations[0].reason == "unsupported_reasoning"
    assert degraded.degradations[0].metadata == {
        "option": AI_MODEL_REASONING_EFFORT_OPTION,
        "requested_effort": "high",
    }
    assert rejected.action == "reject"
    assert rejected.reason == "unsupported_reasoning"
    assert invalid.action == "invoke"
    assert AI_MODEL_REASONING_EFFORT_OPTION not in invalid.options
    assert invalid.degradations[0].kind == "reasoning_omitted"
    assert invalid.degradations[0].reason == "invalid_reasoning_effort"


def test_model_call_planning_uses_model_reasoning_effort_set() -> None:
    supported_low_only = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_reasoning=True,
            reasoning_efforts=frozenset({"low"}),
            supported_options=frozenset({AI_MODEL_REASONING_EFFORT_OPTION}),
        ),
        suffix="reasoning-low",
    )

    degraded = plan_model_call(
        selected=supported_low_only,
        options=AIModelCallOptions(values={AI_MODEL_REASONING_EFFORT_OPTION: "medium"}),
    )
    rejected = plan_model_call(
        selected=supported_low_only,
        options=AIModelCallOptions(
            values={AI_MODEL_REASONING_EFFORT_OPTION: "medium"},
            required=frozenset({AI_MODEL_REASONING_EFFORT_OPTION}),
        ),
    )

    assert degraded.action == "invoke"
    assert degraded.options[AI_MODEL_REASONING_EFFORT_OPTION] == "low"
    assert degraded.degradations[0].kind == "reasoning_effort_adjusted"
    assert degraded.degradations[0].reason == "unsupported_reasoning_effort"
    assert degraded.degradations[0].metadata == {
        "option": AI_MODEL_REASONING_EFFORT_OPTION,
        "requested_effort": "medium",
        "applied_effort": "low",
    }
    assert rejected.action == "reject"
    assert rejected.reason == "unsupported_reasoning_effort"


def test_streaming_planning_does_not_bypass_required_options() -> None:
    selected = _selected_with_capabilities(
        AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            supports_streaming=True,
            supported_options=frozenset({"temperature"}),
        )
    )

    plan = plan_model_call(
        selected=selected,
        requirements=AIModelCallRequirements(
            streaming="required",
            required_options=frozenset({"seed"}),
        ),
        options=AIModelCallOptions(values={"temperature": 0.2, "seed": 1}),
    )

    assert plan.action == "reject"
    assert plan.reason == "unsupported_required_option"
    assert "seed" in (plan.diagnostic or "")


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


def test_openai_compatible_adapter_forwards_reasoning_effort(
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
                options={AI_MODEL_REASONING_EFFORT_OPTION: "medium"},
            )
        )
    )

    assert payloads[0]["reasoning_effort"] == "medium"


def test_anthropic_compatible_adapter_forwards_reasoning_effort(
    monkeypatch: Any,
) -> None:
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(
        anthropic_compatible,
        "AsyncAnthropic",
        lambda **_kwargs: _AnthropicClientStub(payloads),
    )
    provider = anthropic_compatible.AnthropicCompatibleProvider(
        api_base="https://api.example.test/v1",
        api_key="test-key",
    )

    asyncio.run(
        provider.generate_text(
            AIModelGenerateRequest(
                source_id="source-1",
                model_name="claude-1",
                messages=(AIModelMessage(role="user", content="hello"),),
                options={AI_MODEL_REASONING_EFFORT_OPTION: "high"},
            )
        )
    )

    assert payloads[0]["thinking"] == {"type": "adaptive"}
    assert payloads[0]["output_config"] == {"effort": "high"}


def test_anthropic_compatible_adapter_extracts_model_reasoning_efforts() -> None:
    page = SimpleNamespace(
        data=[
            SimpleNamespace(
                id="claude-sonnet-4-5",
                display_name="Claude Sonnet 4.5",
                capabilities={
                    "thinking": {"supported": True},
                    "effort": {
                        "low": {"supported": True},
                        "medium": {"supported": True},
                        "high": {"supported": False},
                        "xhigh": {"supported": True},
                    },
                },
            )
        ]
    )

    models = anthropic_compatible._extract_anthropic_models(page)

    assert models[0].capability_metadata == {
        "reasoning": {"supported": True, "efforts": ["low", "medium"]},
        "supported_options": [AI_MODEL_REASONING_EFFORT_OPTION],
    }


def test_response_normalization_strips_think_blocks_from_visible_text() -> None:
    sanitized = sanitize_visible_reasoning(
        "Hi <think>private</think> there <THINK>x</THINK>!"
    )
    unclosed = sanitize_visible_reasoning("answer <think>private")

    assert sanitized.text == "Hi  there !"
    assert sanitized.reasoning_stripped is True
    assert sanitized.metadata == {
        "visible_reasoning_stripped": True,
        "stripped_reasoning_blocks": 2,
    }
    assert unclosed.text == "answer"
    assert unclosed.metadata["visible_reasoning_stripped"] is True
    assert "private" not in unclosed.metadata


def test_openai_compatible_adapter_forwards_image_url_content_part(
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
                messages=(
                    AIModelMessage(
                        role="user",
                        content="look\n[image: a cat]",
                        parts=(
                            AIModelContentPart(
                                kind="text",
                                text="look\n[image: a cat]",
                            ),
                            AIModelContentPart.image(
                                url="https://cdn.example.test/cat.png",
                                mime_type="image/png",
                            ),
                        ),
                    ),
                ),
            )
        )
    )

    assert payloads[0]["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "look\n[image: a cat]"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://cdn.example.test/cat.png"},
                },
            ],
        }
    ]


def test_openai_compatible_adapter_normalizes_speech_responses(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        openai_compatible,
        "_build_openai_client",
        lambda **_kwargs: _OpenAISpeechClientStub(),
    )
    provider = openai_compatible.OpenAICompatibleProvider(
        api_base="https://api.example.test/v1",
        api_key="test-key",
    )

    transcription = asyncio.run(
        provider.transcribe_audio(
            __import__(
                "apeiria.ai.model.runtime.adapter",
                fromlist=["AIModelTranscriptionRequest"],
            ).AIModelTranscriptionRequest(
                source_id="source-1",
                model_name="whisper-1",
                audio_bytes=b"audio",
                file_name="voice.ogg",
                mime_type="audio/ogg",
            )
        )
    )
    speech = asyncio.run(
        provider.synthesize_speech(
            __import__(
                "apeiria.ai.model.runtime.adapter",
                fromlist=["AIModelSpeechRequest"],
            ).AIModelSpeechRequest(
                source_id="source-1",
                model_name="tts-1",
                text="hello",
                voice="verse",
                response_format="mp3",
            )
        )
    )

    assert transcription.text == "hello transcript"
    assert transcription.raw == {"text": "hello transcript"}
    assert speech.audio_bytes == b"mp3-bytes"
    assert speech.response_format == "mp3"


def test_openai_compatible_adapter_normalizes_streaming_text_events(
    monkeypatch: Any,
) -> None:
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(
        openai_compatible,
        "_build_openai_client",
        lambda **_kwargs: _OpenAIStreamClientStub(payloads),
    )
    provider = openai_compatible.OpenAICompatibleProvider(
        api_base="https://api.example.test/v1",
        api_key="test-key",
    )

    async def collect_events() -> list[AIModelStreamEvent]:
        return [
            event
            async for event in provider.stream_text(
                AIModelStreamRequest(
                    source_id="source-1",
                    model_name="model-1",
                    messages=(AIModelMessage(role="user", content="hello"),),
                )
            )
        ]

    events = asyncio.run(collect_events())

    assert payloads[0]["stream"] is True
    assert [event.kind for event in events] == [
        "start",
        "text_delta",
        "text_delta",
        "final",
    ]
    assert events[1].content_delta == "hel"
    assert events[2].content_delta == "lo"
    assert events[3].response is not None
    assert events[3].response.content == "hello"
    assert events[3].response.finish_reason == "stop"
    assert events[3].response.response_id == "chatcmpl-stream-1"


def test_openai_compatible_streaming_strips_think_delta_text(
    monkeypatch: Any,
) -> None:
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(
        openai_compatible,
        "_build_openai_client",
        lambda **_kwargs: _OpenAIStreamClientStub(
            payloads,
            chunks=(
                _openai_stream_chunk("chatcmpl-stream-2", content_delta="visible "),
                _openai_stream_chunk("chatcmpl-stream-2", content_delta="<think>"),
                _openai_stream_chunk("chatcmpl-stream-2", content_delta="secret"),
                _openai_stream_chunk("chatcmpl-stream-2", content_delta="</think>"),
                _openai_stream_chunk("chatcmpl-stream-2", content_delta=" reply"),
                _openai_stream_chunk("chatcmpl-stream-2", finish_reason="stop"),
            ),
        ),
    )
    provider = openai_compatible.OpenAICompatibleProvider(
        api_base="https://api.example.test/v1",
        api_key="test-key",
    )

    async def collect_events() -> list[AIModelStreamEvent]:
        return [
            event
            async for event in provider.stream_text(
                AIModelStreamRequest(
                    source_id="source-1",
                    model_name="model-1",
                    messages=(AIModelMessage(role="user", content="hello"),),
                )
            )
        ]

    events = asyncio.run(collect_events())

    assert [event.content_delta for event in events if event.kind == "text_delta"] == [
        "visible ",
        " reply",
    ]
    final = events[-1].response
    assert final is not None
    assert final.content == "visible  reply"
    assert final.provider_data == {
        "visible_reasoning_stripped": True,
        "stripped_reasoning_blocks": 1,
    }


def test_gemini_native_adapter_normalizes_chat_catalog_and_embeddings(
    monkeypatch: Any,
) -> None:
    requests: list[tuple[str, str, dict[str, Any] | None]] = []

    async def request(spec: Any) -> _HTTPResponseStub:
        payload = spec.json
        requests.append(
            (spec.method, spec.url, payload if isinstance(payload, dict) else None)
        )
        if spec.url.endswith(":generateContent"):
            return _HTTPResponseStub(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "gemini ok"},
                                ]
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 3},
                }
            )
        if spec.url.endswith(":embedContent"):
            return _HTTPResponseStub(
                {
                    "embedding": {
                        "values": [0.1, 0.2, 0.3],
                    }
                }
            )
        return _HTTPResponseStub(
            {
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "displayName": "Gemini 2.5 Flash",
                    }
                ]
            }
        )

    monkeypatch.setattr(gemini_native, "_request_json", request)
    provider = gemini_native.GeminiNativeProvider(
        api_base="https://generativelanguage.googleapis.com/v1beta",
        api_key="test-key",
    )

    async def scenario() -> tuple[Any, Any, Any]:
        generated = await provider.generate_text(
            AIModelGenerateRequest(
                source_id="source-1",
                model_name="gemini-2.5-flash",
                messages=(AIModelMessage(role="user", content="hello"),),
                max_tokens=_TEST_MAX_TOKENS,
            )
        )
        models = await provider.list_models()
        embeddings = await provider.embed_texts(
            __import__(
                "apeiria.ai.model.runtime.adapter",
                fromlist=["AIModelEmbeddingRequest"],
            ).AIModelEmbeddingRequest(
                source_id="source-1",
                model_name="text-embedding-004",
                texts=("hello",),
            )
        )
        return generated, models, embeddings

    generated, models, embeddings = asyncio.run(scenario())

    assert generated.content == "gemini ok"
    assert generated.usage == {"promptTokenCount": 3}
    assert generated.finish_reason == "STOP"
    assert models[0].id == "gemini-2.5-flash"
    assert models[0].name == "Gemini 2.5 Flash"
    assert embeddings.vectors == ((0.1, 0.2, 0.3),)
    assert requests[0][1].endswith("/models/gemini-2.5-flash:generateContent")
    assert requests[0][2]["generationConfig"]["maxOutputTokens"] == _TEST_MAX_TOKENS


def test_ollama_native_adapter_normalizes_chat_catalog_and_embeddings(
    monkeypatch: Any,
) -> None:
    requests: list[tuple[str, str, dict[str, Any] | None]] = []

    async def request(spec: Any) -> _HTTPResponseStub:
        payload = spec.json
        requests.append(
            (spec.method, spec.url, payload if isinstance(payload, dict) else None)
        )
        if spec.url.endswith("/api/chat"):
            return _HTTPResponseStub(
                {
                    "message": {"content": "ollama ok"},
                    "done_reason": "stop",
                    "prompt_eval_count": 2,
                    "eval_count": 4,
                }
            )
        if spec.url.endswith("/api/embed"):
            return _HTTPResponseStub(
                {
                    "embeddings": [
                        [0.1, 0.2],
                        [0.3, 0.4],
                    ]
                }
            )
        return _HTTPResponseStub(
            {
                "models": [
                    {
                        "name": "qwen3:8b",
                        "model": "qwen3:8b",
                    }
                ]
            }
        )

    monkeypatch.setattr(ollama_native, "_request_json", request)
    provider = ollama_native.OllamaNativeProvider(
        api_base="http://127.0.0.1:11434",
    )

    async def scenario() -> tuple[Any, Any, Any]:
        generated = await provider.generate_text(
            AIModelGenerateRequest(
                source_id="source-1",
                model_name="qwen3:8b",
                messages=(AIModelMessage(role="user", content="hello"),),
                max_tokens=_TEST_MAX_TOKENS,
            )
        )
        models = await provider.list_models()
        embeddings = await provider.embed_texts(
            __import__(
                "apeiria.ai.model.runtime.adapter",
                fromlist=["AIModelEmbeddingRequest"],
            ).AIModelEmbeddingRequest(
                source_id="source-1",
                model_name="nomic-embed-text",
                texts=("hello", "world"),
            )
        )
        return generated, models, embeddings

    generated, models, embeddings = asyncio.run(scenario())

    assert generated.content == "ollama ok"
    assert generated.usage == {"prompt_eval_count": 2, "eval_count": 4}
    assert generated.finish_reason == "stop"
    assert models[0].id == "qwen3:8b"
    assert models[0].name == "qwen3:8b"
    assert embeddings.vectors == ((0.1, 0.2), (0.3, 0.4))
    assert requests[0][1].endswith("/api/chat")
    assert requests[0][2]["options"]["num_predict"] == _TEST_MAX_TOKENS


def test_native_protocol_adapters_report_unsupported_operations() -> None:
    gemini = gemini_native.GeminiNativeProvider(
        api_base="https://generativelanguage.googleapis.com/v1beta",
        api_key="test-key",
    )
    ollama = ollama_native.OllamaNativeProvider(
        api_base="http://127.0.0.1:11434",
    )

    with raises(gemini_native.GeminiNativeProviderCapabilityError):
        asyncio.run(
            gemini.rerank_documents(
                __import__(
                    "apeiria.ai.model.runtime.adapter",
                    fromlist=["AIModelRerankRequest"],
                ).AIModelRerankRequest(
                    source_id="source-1",
                    model_name="gemini-2.5-flash",
                    query="hello",
                    documents=("doc",),
                )
            )
        )
    with raises(ollama_native.OllamaNativeProviderCapabilityError):
        asyncio.run(
            ollama.synthesize_speech(
                __import__(
                    "apeiria.ai.model.runtime.adapter",
                    fromlist=["AIModelSpeechRequest"],
                ).AIModelSpeechRequest(
                    source_id="source-1",
                    model_name="qwen3:8b",
                    text="hello",
                )
            )
        )


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


def test_response_contract_exposes_sanitized_visible_text_metadata() -> None:
    response = AIModelGenerateResponse(
        source_id="source-1",
        model_name="model-1",
        content="hello <think>secret</think> world",
    )

    normalized = response.with_sanitized_visible_text()

    assert normalized.content == "hello  world"
    assert normalized.provider_data == {
        "visible_reasoning_stripped": True,
        "stripped_reasoning_blocks": 1,
    }
    assert "secret" not in normalized.content
    assert "secret" not in str(normalized.provider_data)


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


class _SpeechClientStub:
    def __init__(self) -> None:
        self.transcription_requests: list[Any] = []
        self.speech_requests: list[Any] = []

    async def transcribe_audio(self, request: Any) -> AIModelTranscriptionResponse:
        self.transcription_requests.append(request)
        return AIModelTranscriptionResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            text="transcribed",
        )

    async def synthesize_speech(self, request: Any) -> AIModelSpeechResponse:
        self.speech_requests.append(request)
        return AIModelSpeechResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            audio_bytes=b"speech",
            response_format=request.response_format,
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


class _AnthropicClientStub:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.messages = SimpleNamespace(create=self._create_message)
        self._payloads = payloads

    async def _create_message(self, **payload: Any) -> Any:
        self._payloads.append(payload)

        def model_dump(**_kwargs: Any) -> dict[str, Any]:
            return {
                "id": "msg-1",
                "usage": {"input_tokens": 1},
                "model": payload.get("model"),
            }

        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            model_dump=model_dump,
        )

    async def close(self) -> None:
        return None


class _OpenAISpeechClientStub:
    def __init__(self) -> None:
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create_transcription),
            speech=SimpleNamespace(create=self._create_speech),
        )

    async def _create_transcription(self, **_payload: Any) -> Any:
        return SimpleNamespace(
            text="hello transcript",
            model_dump=lambda **_kwargs: {"text": "hello transcript"},
        )

    async def _create_speech(self, **_payload: Any) -> Any:
        return SimpleNamespace(content=b"mp3-bytes")

    async def close(self) -> None:
        return None


class _OpenAIStreamClientStub:
    def __init__(
        self,
        payloads: list[dict[str, Any]],
        *,
        chunks: tuple[Any, ...] | None = None,
    ) -> None:
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create_completion)
        )
        self._payloads = payloads
        self._chunks = chunks

    async def _create_completion(self, **payload: Any) -> Any:
        self._payloads.append(payload)
        return _OpenAIStreamStub(self._chunks)

    async def close(self) -> None:
        return None


class _HTTPResponseStub:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= _HTTP_BAD_REQUEST:
            raise RuntimeError


class _OpenAIStreamStub:
    def __init__(self, chunks: tuple[Any, ...] | None = None) -> None:
        self._chunks = chunks

    def __aiter__(self) -> Any:
        return self._events()

    async def _events(self) -> Any:
        chunks = self._chunks or (
            _openai_stream_chunk("chatcmpl-stream-1", content_delta="hel"),
            _openai_stream_chunk("chatcmpl-stream-1", content_delta="lo"),
            _openai_stream_chunk("chatcmpl-stream-1", finish_reason="stop"),
        )
        for chunk in chunks:
            yield chunk


def _openai_stream_chunk(
    response_id: str,
    *,
    content_delta: str | None = None,
    finish_reason: str | None = None,
) -> Any:
    def model_dump(**_kwargs: Any) -> dict[str, Any]:
        return {"id": response_id}

    return SimpleNamespace(
        id=response_id,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content_delta),
                finish_reason=finish_reason,
            )
        ],
        model_dump=model_dump,
    )
