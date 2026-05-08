from __future__ import annotations

import json
from dataclasses import replace

from apeiria.ai.model.runtime.adapter import AIModelContentPart, AIModelMessage
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallRequirements,
    AIModelCapabilities,
)
from apeiria.ai.model.runtime.planning import plan_model_call
from apeiria.app.ai.runtime.session.context import (
    RuntimeMediaDiagnostic,
    RuntimeSourceMediaPart,
    RuntimeTurnSource,
)
from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
from apeiria.app.ai.runtime.trace import project_turn_trace
from tests.ai.test_model_provider_capabilities import _selected_with_capabilities


def test_runtime_turn_source_defaults_to_text_only_media_shape() -> None:
    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
    )

    assert source.media_parts == ()
    assert source.media_diagnostics == ()


def test_runtime_source_media_part_builds_image_model_part() -> None:
    media = RuntimeSourceMediaPart(
        kind="image",
        url="https://cdn.example.test/cat.png",
        mime_type="image/png",
        fallback_text="[image: a cat]",
        metadata={"alt": "a cat", "token": "secret"},
    )

    part = media.to_model_content_part()

    assert part == AIModelContentPart.image(
        url="https://cdn.example.test/cat.png",
        mime_type="image/png",
    )
    assert "token" not in str(media.safe_metadata())


def test_live_runtime_extracts_media_parts_from_persisted_content() -> None:
    from apeiria.app.ai.runtime.live import extract_runtime_media

    media = extract_runtime_media(
        json.dumps(
            {
                "segments": [
                    {"type": "text", "text": "look"},
                    {
                        "type": "image",
                        "url": "https://cdn.example.test/cat.png",
                        "mime": "image/png",
                        "alt": "a cat",
                        "token": "secret",
                    },
                    {
                        "type": "record",
                        "asset_id": "asset-voice",
                        "mime": "audio/ogg",
                        "size": 1024,
                    },
                    {"type": "image", "file": "private-only.png"},
                ]
            }
        )
    )

    parts = media.parts
    assert parts == (
        RuntimeSourceMediaPart(
            kind="image",
            fallback_text="[image: a cat]",
            url="https://cdn.example.test/cat.png",
            mime_type="image/png",
            required=True,
            metadata={"alt": "a cat"},
        ),
        RuntimeSourceMediaPart(
            kind="audio",
            fallback_text="[audio]",
            asset_id="asset-voice",
            mime_type="audio/ogg",
            size_bytes=1024,
            required=True,
        ),
    )
    assert media.diagnostics == (
        RuntimeMediaDiagnostic(
            kind="image",
            reason="missing_safe_reference",
            segment_type="image",
        ),
    )
    assert "secret" not in str(parts)


def test_project_turn_source_media_keeps_text_fallback_with_current_turn() -> None:
    from apeiria.app.ai.runtime.multimodal import project_media_into_messages

    messages = (
        AIModelMessage(role="system", content="persona"),
        AIModelMessage(role="user", content="look"),
    )
    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text="look",
        source_message_id="msg-1",
        user_id="user-1",
        media_parts=(
            RuntimeSourceMediaPart(
                kind="image",
                url="https://cdn.example.test/cat.png",
                mime_type="image/png",
                fallback_text="[image: a cat]",
                required=True,
            ),
        ),
    )

    projected, diagnostics = project_media_into_messages(messages, source=source)

    assert projected[0] == messages[0]
    assert projected[1].role == "user"
    assert projected[1].content == "look\n[image: a cat]"
    assert projected[1].parts == (
        AIModelContentPart(kind="text", text="look\n[image: a cat]"),
        AIModelContentPart.image(
            url="https://cdn.example.test/cat.png",
            mime_type="image/png",
            required=True,
        ),
    )
    assert diagnostics["media_counts"] == {"image": 1}
    assert "https://cdn.example.test/cat.png" not in str(diagnostics)


def test_project_turn_source_media_leaves_text_only_messages_unchanged() -> None:
    from apeiria.app.ai.runtime.multimodal import project_media_into_messages

    messages = (AIModelMessage(role="user", content="hello"),)
    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
    )

    projected, diagnostics = project_media_into_messages(messages, source=source)

    assert projected == messages
    assert diagnostics == {}


def test_multimodal_trace_metadata_is_bounded_and_sanitized() -> None:
    strategy = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={},
        should_observe=True,
        should_reply=True,
    )
    turn_result = __import__(
        "apeiria.app.ai.agent_turn",
        fromlist=["AgentTurnResult"],
    ).AgentTurnResult(
        trace_id="trace-media",
        runtime_mode="message",
        status="completed",
        finish_reason="direct_model_completed",
        response_source="direct",
        metadata={
            "prompt_diagnostics": {
                "multimodal": {
                    "projected": True,
                    "media_counts": {"image": 1},
                    "source_url": "https://cdn.example.test/cat.png",
                }
            },
            "capability_degradations": [
                {
                    "kind": "modalities_replaced",
                    "reason": "unsupported_optional_modality",
                    "detail": "unsupported optional modalities replaced: image",
                    "metadata": {"modalities": ["image"]},
                }
            ],
        },
    )

    metadata = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=turn_result,
    ).to_metadata()

    assert metadata["multimodal"] == {
        "projected": True,
        "media_counts": {"image": 1},
    }
    assert metadata["capability_degradations"] == [
        {
            "kind": "modalities_replaced",
            "reason": "unsupported_optional_modality",
            "metadata": {"modalities": ["image"]},
        }
    ]
    assert "https://cdn.example.test/cat.png" not in str(metadata)


def test_required_runtime_media_uses_capable_fallback_after_primary_rejection() -> None:
    primary = _selected_with_capabilities(
        AIModelCapabilities(input_modalities=frozenset({"text"})),
        suffix="primary",
        fallback_profile_id="profile-fallback",
    )
    fallback = _selected_with_capabilities(
        AIModelCapabilities(input_modalities=frozenset({"text", "image"})),
        suffix="fallback",
    )
    messages = (
        AIModelMessage(
            role="user",
            content="look",
            parts=(AIModelContentPart.image(url="https://example.test/cat.png"),),
        ),
    )

    primary_plan = plan_model_call(
        selected=primary,
        messages=messages,
        requirements=AIModelCallRequirements(required_modalities=frozenset({"image"})),
    )
    fallback_plan = plan_model_call(
        selected=fallback,
        messages=messages,
        requirements=AIModelCallRequirements(required_modalities=frozenset({"image"})),
    )

    assert primary_plan.action == "reject"
    assert primary_plan.reason == "unsupported_modality"
    assert fallback_plan.action == "invoke"


def test_optional_runtime_media_degrades_without_mutating_original_message() -> None:
    selected = _selected_with_capabilities(
        AIModelCapabilities(input_modalities=frozenset({"text"})),
    )
    message = AIModelMessage(
        role="user",
        content="look\n[image: a cat]",
        parts=(
            AIModelContentPart(kind="text", text="look\n[image: a cat]"),
            AIModelContentPart.image(
                url="https://example.test/cat.png",
                required=False,
            ),
        ),
    )

    plan = plan_model_call(
        selected=selected,
        messages=(message,),
        requirements=AIModelCallRequirements(optional_modalities=frozenset({"image"})),
    )

    assert plan.action == "invoke"
    assert plan.messages[0].parts == (
        AIModelContentPart(kind="text", text="look\n[image: a cat]"),
    )
    assert plan.degradations[0].kind == "modalities_replaced"
    assert replace(message).parts[-1].kind == "image"
