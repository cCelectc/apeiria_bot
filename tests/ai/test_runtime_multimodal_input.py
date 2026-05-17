from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED_EXTRACTED_MEDIA_COUNT = 2
EXPECTED_AUDIO_SIZE = 12
EXPECTED_IMAGE_BYTES_SIZE = 8
PNG_BASE64 = "cG5n"
WAV_BASE64 = "d2F2"


def test_extract_runtime_media_preserves_file_and_path_references(
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.runtime.live import extract_runtime_media

    audio_path = tmp_path / "voice.wav"
    content_json = json.dumps(
        {
            "segments": [
                {
                    "type": "image",
                    "file": "cat.png",
                    "mime": "image/png",
                    "alt": "cat",
                },
                {
                    "type": "record",
                    "path": str(audio_path),
                    "mime": "audio/wav",
                    "size": "12",
                },
                {"type": "file", "name": "missing.pdf"},
            ]
        }
    )

    result = extract_runtime_media(content_json)

    assert len(result.parts) == EXPECTED_EXTRACTED_MEDIA_COUNT
    assert result.parts[0].kind == "image"
    assert result.parts[0].file_ref == "cat.png"
    assert result.parts[0].fallback_text == "[image: cat]"
    assert result.parts[1].kind == "audio"
    assert result.parts[1].path_ref == str(audio_path)
    assert result.parts[1].size_bytes == EXPECTED_AUDIO_SIZE
    assert [(item.kind, item.reason) for item in result.diagnostics] == [
        ("file", "missing_safe_reference")
    ]


def test_extract_runtime_media_preserves_base64_references() -> None:
    from apeiria.app.ai.runtime.live import extract_runtime_media

    result = extract_runtime_media(
        json.dumps(
            {
                "segments": [
                    {
                        "type": "image",
                        "base64": PNG_BASE64,
                        "mime": "image/png",
                    },
                    {
                        "type": "record",
                        "file": f"base64://{WAV_BASE64}",
                        "mime": "audio/wav",
                    },
                ]
            }
        )
    )

    assert [part.kind for part in result.parts] == ["image", "audio"]
    assert result.parts[0].base64_data == PNG_BASE64
    assert result.parts[1].base64_data == f"base64://{WAV_BASE64}"
    assert result.parts[1].file_ref is None


def test_prepare_runtime_media_parts_reads_file_and_reports_unresolved(
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.runtime.media import prepare_runtime_media_parts
    from apeiria.app.ai.runtime.session.context import RuntimeSourceMediaPart

    image_path = tmp_path / "cat.png"
    image_path.write_bytes(b"png-data")

    result = prepare_runtime_media_parts(
        (
            RuntimeSourceMediaPart(
                kind="image",
                path_ref=str(image_path),
                mime_type="image/png",
                file_name="cat.png",
            ),
            RuntimeSourceMediaPart(
                kind="file",
                file_ref="missing.pdf",
                mime_type="application/pdf",
            ),
        )
    )

    assert len(result.parts) == 1
    assert result.parts[0].kind == "image"
    assert result.parts[0].data == b"png-data"
    assert result.parts[0].mime_type == "image/png"
    assert result.parts[0].metadata["file_name"] == "cat.png"
    assert result.parts[0].metadata["size_bytes"] == EXPECTED_IMAGE_BYTES_SIZE
    assert result.parts[0].metadata["source_kind"] == "local_file"
    assert result.diagnostics[-1]["status"] == "unresolved"
    assert result.diagnostics[-1]["kind"] == "file"


def test_prepare_runtime_media_parts_reads_base64_data() -> None:
    from apeiria.app.ai.runtime.media import prepare_runtime_media_parts
    from apeiria.app.ai.runtime.session.context import RuntimeSourceMediaPart

    result = prepare_runtime_media_parts(
        (
            RuntimeSourceMediaPart(
                kind="image",
                base64_data=PNG_BASE64,
                mime_type="image/png",
            ),
        )
    )

    assert len(result.parts) == 1
    assert result.parts[0].data == b"png"
    assert result.parts[0].metadata["source_kind"] == "base64"


def test_project_media_into_messages_attaches_prepared_parts(
    tmp_path: Path,
) -> None:
    from apeiria.ai.model.runtime.adapter import AIModelMessage
    from apeiria.app.ai.runtime.multimodal import project_media_into_messages
    from apeiria.app.ai.runtime.session.context import (
        RuntimeSourceMediaPart,
        RuntimeTurnSource,
    )

    image_path = tmp_path / "cat.png"
    image_path.write_bytes(b"png-data")
    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text="look",
        source_message_id="msg-1",
        user_id="user-1",
        media_parts=(
            RuntimeSourceMediaPart(
                kind="image",
                fallback_text="[image: cat]",
                path_ref=str(image_path),
                mime_type="image/png",
            ),
        ),
    )

    projected, diagnostics = project_media_into_messages(
        (AIModelMessage(role="user", content="look"),),
        source=source,
    )

    assert projected[0].content == "look\n[image: cat]"
    assert [part.kind for part in projected[0].parts] == ["text", "image"]
    assert projected[0].parts[1].data == b"png-data"
    assert diagnostics["multimodal"]["projected"] is True
    assert diagnostics["multimodal"]["media_counts"] == {"image": 1}


def test_media_only_private_input_passes_wake_and_hard_rules() -> None:
    from datetime import datetime, timezone

    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.reply_strategy.wake_gate import evaluate_wake
    from apeiria.app.ai.runtime.planning.hard_rules import decide_runtime_hard_rule
    from apeiria.app.ai.runtime.session.context import (
        RuntimeMediaDiagnostic,
        RuntimeTurnSource,
    )

    wake = WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text="",
        is_tome=False,
        is_private=True,
        is_future_task=False,
        has_media=True,
    )
    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text="",
        source_message_id="msg-1",
        user_id="user-1",
        is_private=True,
        media_diagnostics=(
            RuntimeMediaDiagnostic(
                kind="image",
                reason="missing_safe_reference",
                segment_type="image",
            ),
        ),
    )

    assert evaluate_wake(wake).reason == "private_message"
    decision = decide_runtime_hard_rule(
        wake_context=wake,
        source=source,
        now=datetime(2026, 5, 17, tzinfo=timezone.utc),
    )

    assert decision.should_reply is True
    assert decision.reason_codes == ("private_message",)


def test_speech_preparation_consumes_transcribed_audio(tmp_path: Path) -> None:
    from apeiria.app.ai.runtime.session.context import (
        RuntimeSourceMediaPart,
        RuntimeTurnInput,
        RuntimeTurnSource,
    )
    from apeiria.app.ai.runtime.speech import prepare_speech_input
    from apeiria.conversation.models import ChatSessionIdentity

    audio_path = tmp_path / "voice.wav"
    audio_path.write_bytes(b"wav-data")
    turn = RuntimeTurnInput(
        identity=ChatSessionIdentity(
            session_id="onebot:bot-1:private:user-1",
            platform="onebot",
            bot_id="bot-1",
            scene_type="private",
            scene_id="user-1",
            subject_id="user-1",
        ),
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="typed",
            source_message_id="msg-1",
            user_id="user-1",
            media_parts=(
                RuntimeSourceMediaPart(
                    kind="audio",
                    path_ref=str(audio_path),
                    mime_type="audio/wav",
                    file_name="voice.wav",
                ),
            ),
        ),
        sender_id="bot-1",
    )

    class Selector:
        async def select_stt_model(self) -> object:
            return _selected_stt_model()

    class Transcriber:
        async def transcribe(self, **_: object) -> object:
            return _Response(text="hello from audio")

    result = asyncio.run(
        prepare_speech_input(
            turn,
            stt_input_enabled=True,
            audio_resolver=_DefaultResolverProxy(),
            model_selector=Selector(),
            transcriber=Transcriber(),
        )
    )

    assert result.turn.message_text == "typed\n[transcribed speech] hello from audio"
    assert result.turn.source.media_parts == ()
    assert result.turn.source.speech_diagnostics[0]["status"] == "transcribed"


def test_speech_preparation_consumes_base64_audio() -> None:
    from apeiria.app.ai.runtime.session.context import (
        RuntimeSourceMediaPart,
        RuntimeTurnInput,
        RuntimeTurnSource,
    )
    from apeiria.app.ai.runtime.speech import prepare_speech_input
    from apeiria.conversation.models import ChatSessionIdentity

    turn = RuntimeTurnInput(
        identity=ChatSessionIdentity(
            session_id="onebot:bot-1:private:user-1",
            platform="onebot",
            bot_id="bot-1",
            scene_type="private",
            scene_id="user-1",
            subject_id="user-1",
        ),
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="",
            source_message_id="msg-1",
            user_id="user-1",
            media_parts=(
                RuntimeSourceMediaPart(
                    kind="audio",
                    base64_data=WAV_BASE64,
                    mime_type="audio/wav",
                    file_name="voice.wav",
                ),
            ),
        ),
        sender_id="bot-1",
    )

    class Selector:
        async def select_stt_model(self) -> object:
            return _selected_stt_model()

    class Transcriber:
        async def transcribe(self, **kwargs: object) -> object:
            assert kwargs["audio_bytes"] == b"wav"
            return _Response(text="decoded audio")

    result = asyncio.run(
        prepare_speech_input(
            turn,
            stt_input_enabled=True,
            audio_resolver=_DefaultResolverProxy(),
            model_selector=Selector(),
            transcriber=Transcriber(),
        )
    )

    assert result.turn.message_text == "decoded audio"
    assert result.turn.source.media_parts == ()
    assert result.turn.source.speech_diagnostics[0]["source_kind"] == "base64"


def test_model_planning_rejects_required_and_degrades_optional_media() -> None:
    from apeiria.ai.model.runtime.adapter import AIModelContentPart, AIModelMessage
    from apeiria.ai.model.runtime.capabilities import (
        AIModelCallRequirements,
        AIModelCapabilities,
    )
    from apeiria.ai.model.runtime.planning import plan_model_call
    from tests.ai.agent_turn_helpers import selected_model

    selected = selected_model("text-only")
    required = (
        AIModelMessage(
            role="user",
            content="look",
            parts=(
                AIModelContentPart(kind="text", text="look"),
                AIModelContentPart(kind="image", data=b"png", mime_type="image/png"),
            ),
        ),
    )

    rejected = plan_model_call(selected=selected, messages=required)

    assert rejected.action == "reject"
    assert rejected.reason == "unsupported_modality"

    optional = plan_model_call(
        selected=selected,
        messages=required,
        requirements=AIModelCallRequirements(optional_modalities=frozenset({"image"})),
    )

    assert optional.action == "invoke"
    assert optional.messages[0].parts == (AIModelContentPart(kind="text", text="look"),)
    assert optional.degradations[0].kind == "modalities_replaced"

    image_model = selected_model("image")
    object.__setattr__(
        image_model,
        "resolved_capabilities",
        AIModelCapabilities(input_modalities=frozenset({"text", "image"})),
    )
    accepted = plan_model_call(selected=image_model, messages=required)

    assert accepted.action == "invoke"
    assert accepted.messages[0].parts == required[0].parts


def test_openai_content_parts_serialize_media_and_degrade_unrepresentable() -> None:
    from apeiria.ai.model.adapters.openai_compatible import _build_openai_content_parts
    from apeiria.ai.model.runtime.adapter import AIModelContentPart, AIModelMessage

    content = _build_openai_content_parts(
        AIModelMessage(
            role="user",
            content="",
            parts=(
                AIModelContentPart(kind="text", text="inspect"),
                AIModelContentPart(kind="image", data=b"png", mime_type="image/png"),
                AIModelContentPart(kind="audio", data=b"wav", mime_type="audio/wav"),
                AIModelContentPart(
                    kind="file",
                    data=b"pdf",
                    mime_type="application/pdf",
                    metadata={"file_name": "doc.pdf"},
                ),
                AIModelContentPart(kind="audio", url="https://example.test/a.wav"),
            ),
        )
    )

    assert isinstance(content, list)
    assert [part["type"] for part in content] == [
        "text",
        "image_url",
        "input_audio",
        "file",
        "text",
    ]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[2]["input_audio"]["format"] == "wav"
    assert content[3]["file"]["filename"] == "doc.pdf"
    assert content[-1] == {
        "type": "text",
        "text": "[audio omitted: unsupported content representation]",
    }


def test_gemini_payload_serializes_media_and_degrades_unrepresentable() -> None:
    from apeiria.ai.model.adapters.gemini_native import _build_gemini_generate_payload
    from apeiria.ai.model.runtime.adapter import AIModelContentPart, AIModelMessage

    payload = _build_gemini_generate_payload(
        prompt="",
        messages=(
            AIModelMessage(
                role="user",
                content="",
                parts=(
                    AIModelContentPart(kind="text", text="inspect"),
                    AIModelContentPart(
                        kind="image",
                        data=b"png",
                        mime_type="image/png",
                    ),
                    AIModelContentPart(
                        kind="audio",
                        data=b"wav",
                        mime_type="audio/wav",
                    ),
                    AIModelContentPart(kind="file", required=True),
                ),
            ),
        ),
        tools=(),
        temperature=None,
        max_tokens=None,
        options={},
    )

    parts = payload["contents"][0]["parts"]

    assert parts[0] == {"text": "inspect"}
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    assert parts[2]["inlineData"]["mimeType"] == "audio/wav"
    assert parts[3] == {"text": "[file omitted: unsupported content representation]"}


def test_anthropic_payload_serializes_media_and_degrades_unrepresentable() -> None:
    from apeiria.ai.model.adapters.anthropic_compatible import _build_anthropic_payload
    from apeiria.ai.model.runtime.adapter import AIModelContentPart, AIModelMessage

    _system, chat = _build_anthropic_payload(
        (
            AIModelMessage(
                role="user",
                content="",
                parts=(
                    AIModelContentPart(kind="text", text="inspect"),
                    AIModelContentPart(
                        kind="image",
                        data=b"png",
                        mime_type="image/png",
                    ),
                    AIModelContentPart(
                        kind="file",
                        data=b"pdf",
                        mime_type="application/pdf",
                        metadata={"file_name": "doc.pdf"},
                    ),
                    AIModelContentPart(kind="audio", data=b"wav"),
                ),
            ),
        ),
        "",
    )

    content = chat[0]["content"]

    assert [block["type"] for block in content] == [
        "text",
        "image",
        "document",
        "text",
    ]
    assert content[1]["source"]["media_type"] == "image/png"
    assert content[2]["source"]["media_type"] == "application/pdf"
    assert content[3] == {
        "type": "text",
        "text": "[audio omitted: unsupported content representation]",
    }


def test_ollama_payload_serializes_image_and_degrades_unsupported_media() -> None:
    from apeiria.ai.model.adapters.ollama_native import (
        _build_ollama_chat_payload,
        _ChatPayloadInput,
    )
    from apeiria.ai.model.runtime.adapter import AIModelContentPart, AIModelMessage

    payload = _build_ollama_chat_payload(
        _ChatPayloadInput(
            model_name="llava",
            prompt="",
            messages=(
                AIModelMessage(
                    role="user",
                    content="",
                    parts=(
                        AIModelContentPart(kind="text", text="inspect"),
                        AIModelContentPart(
                            kind="image",
                            data=b"png",
                            mime_type="image/png",
                        ),
                        AIModelContentPart(
                            kind="image",
                            url="https://example.test/cat.png",
                        ),
                        AIModelContentPart(kind="file", data=b"pdf"),
                    ),
                ),
            ),
            temperature=None,
            max_tokens=None,
            options={},
        )
    )

    assert payload["messages"][0]["content"] == (
        "inspect\n"
        "[image omitted: unsupported content representation]\n"
        "[file omitted: unsupported content representation]"
    )
    assert payload["messages"][0]["images"] == ["cG5n"]


@dataclass(frozen=True)
class _Response:
    text: str


class _DefaultResolverProxy:
    def resolve_audio(self, media: object) -> object | None:
        from apeiria.app.ai.runtime.speech import DefaultSpeechAudioResolver

        return DefaultSpeechAudioResolver().resolve_audio(media)  # type: ignore[arg-type]


def _selected_stt_model() -> Any:
    from apeiria.ai.model import (
        AIModelProfileDefinition,
        AISelectedModel,
        AISourceDefinition,
        AISourceModelDefinition,
    )
    from apeiria.ai.model.runtime.capabilities import AIModelCapabilities

    return AISelectedModel(
        source=AISourceDefinition(
            source_id="source-stt",
            name="STT",
            capability_type="speech_to_text",
            client_type="openai",
            preset_type="openai_compatible_stt",
            api_base="https://example.invalid/v1",
            capability_metadata={"input_modalities": ["audio"]},
        ),
        source_model=AISourceModelDefinition(
            model_id="model-stt",
            source_id="source-stt",
            model_identifier="whisper",
            display_name="Whisper",
            capability_metadata={"input_modalities": ["audio"]},
        ),
        profile=AIModelProfileDefinition(
            profile_id="profile-stt",
            name="STT",
            model_id="model-stt",
            task_class="speech_to_text",
            priority=1,
        ),
        resolved_model_name="whisper",
        resolved_capabilities=AIModelCapabilities(
            lanes=frozenset({"speech_to_text"}),
            input_modalities=frozenset({"audio"}),
            output_modalities=frozenset({"text"}),
        ),
    )
