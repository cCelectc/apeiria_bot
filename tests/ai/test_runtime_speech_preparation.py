from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model.catalog.models import AISpeechToTextModelDefinition
from apeiria.ai.model.routing.selection import AISelectedCapabilityModel
from apeiria.ai.model.runtime.adapter import AIModelTranscriptionResponse
from apeiria.ai.model.sources.models import AISourceDefinition
from apeiria.app.ai.runtime.session.context import (
    RuntimeSourceMediaPart,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.conversation.models import ChatSessionIdentity

if TYPE_CHECKING:
    from pathlib import Path


def test_prepare_speech_input_is_disabled_by_default(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"ogg data")
    transcriber = _Transcriber("ignored")
    turn = _turn(
        message_text="",
        media_parts=(
            RuntimeSourceMediaPart(
                kind="audio",
                asset_id="asset-voice",
                mime_type="audio/ogg",
            ),
        ),
    )

    result = asyncio.run(
        _prepare_speech_input(
            turn,
            stt_input_enabled=False,
            audio_resolver=_AudioResolver({"asset-voice": audio_path}),
            model_selector=_ModelSelector(_selected_stt()),
            transcriber=transcriber,
        )
    )

    assert result.turn is turn
    assert transcriber.calls == []
    assert result.diagnostics == (
        {
            "status": "disabled",
            "reason": "stt_input_disabled",
            "audio_count": 1,
        },
    )


def test_prepare_speech_input_transcribes_audio_only_turn(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"ogg data")
    selected = _selected_stt()

    result = asyncio.run(
        _prepare_speech_input(
            _turn(
                message_text="",
                media_parts=(
                    RuntimeSourceMediaPart(
                        kind="audio",
                        asset_id="asset-voice",
                        file_name="voice.ogg",
                        mime_type="audio/ogg",
                        size_bytes=8,
                    ),
                ),
            ),
            stt_input_enabled=True,
            audio_resolver=_AudioResolver({"asset-voice": audio_path}),
            model_selector=_ModelSelector(selected),
            transcriber=_Transcriber("turn transcript"),
        )
    )

    assert result.turn.message_text == "turn transcript"
    assert result.diagnostics == (
        {
            "status": "transcribed",
            "audio_kind": "audio",
            "source_kind": "asset",
            "selected_model": "source-stt:whisper-1",
            "transcript_length": len("turn transcript"),
        },
    )


def test_prepare_speech_input_keeps_typed_text_and_labels_transcript(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"ogg data")

    result = asyncio.run(
        _prepare_speech_input(
            _turn(
                message_text="typed text",
                media_parts=(
                    RuntimeSourceMediaPart(
                        kind="audio",
                        asset_id="asset-voice",
                        mime_type="audio/ogg",
                    ),
                ),
            ),
            stt_input_enabled=True,
            audio_resolver=_AudioResolver({"asset-voice": audio_path}),
            model_selector=_ModelSelector(_selected_stt()),
            transcriber=_Transcriber("spoken text"),
        )
    )

    assert result.turn.message_text == "typed text\n[transcribed speech] spoken text"
    assert result.diagnostics[0]["status"] == "transcribed"


def test_prepare_speech_input_records_bounded_failures(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"ogg data")

    no_model = asyncio.run(
        _prepare_speech_input(
            _turn(
                message_text="typed text",
                media_parts=(
                    RuntimeSourceMediaPart(kind="audio", asset_id="asset-voice"),
                ),
            ),
            stt_input_enabled=True,
            audio_resolver=_AudioResolver({"asset-voice": audio_path}),
            model_selector=_ModelSelector(None),
            transcriber=_Transcriber("ignored"),
        )
    )
    unsupported = asyncio.run(
        _prepare_speech_input(
            _turn(
                message_text="typed text",
                media_parts=(RuntimeSourceMediaPart(kind="audio", url="ftp://bad"),),
            ),
            stt_input_enabled=True,
            audio_resolver=_AudioResolver({}),
            model_selector=_ModelSelector(_selected_stt()),
            transcriber=_Transcriber("ignored"),
        )
    )
    provider_failed = asyncio.run(
        _prepare_speech_input(
            _turn(
                message_text="typed text",
                media_parts=(
                    RuntimeSourceMediaPart(kind="audio", asset_id="asset-voice"),
                ),
            ),
            stt_input_enabled=True,
            audio_resolver=_AudioResolver({"asset-voice": audio_path}),
            model_selector=_ModelSelector(_selected_stt()),
            transcriber=_Transcriber(RuntimeError("api key sk-secret raw payload")),
        )
    )

    assert no_model.turn.message_text == "typed text"
    assert no_model.diagnostics == (
        {
            "status": "speech_to_text_unavailable",
            "reason": "missing_stt_model",
            "audio_count": 1,
        },
    )
    assert unsupported.diagnostics == (
        {
            "status": "unsupported_audio",
            "reason": "unsafe_or_unresolved_audio",
            "audio_kind": "audio",
        },
    )
    assert provider_failed.diagnostics == (
        {
            "status": "transcription_failed",
            "reason": "provider_error",
            "audio_kind": "audio",
        },
    )
    assert "sk-secret" not in str(provider_failed.diagnostics)


def test_trace_projection_exposes_speech_diagnostics_without_audio_payloads() -> None:
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
    from apeiria.app.ai.runtime.trace import project_turn_trace

    result = __import__(
        "apeiria.app.ai.agent_turn",
        fromlist=["AgentTurnResult"],
    ).AgentTurnResult(
        trace_id="trace-speech",
        runtime_mode="message",
        status="completed",
        finish_reason="direct_model_completed",
        response_source="direct",
        metadata={
            "prompt_diagnostics": {
                "speech": [
                    {
                        "status": "transcribed",
                        "audio_kind": "audio",
                        "source_kind": "asset",
                        "selected_model": "source-stt:whisper-1",
                        "transcript_length": 11,
                        "audio_bytes": b"raw",
                        "url": "https://secret.example.test/voice.ogg",
                    }
                ]
            }
        },
    )

    metadata = project_turn_trace(
        session_id="session-1",
        strategy_decision=RuntimeHardRuleDecision(
            action="continue",
            reason_codes=("direct_signal",),
            reason_text="direct",
            evidence={},
            should_observe=True,
            should_reply=True,
        ),
        turn_result=result,
    ).to_metadata()

    assert metadata["speech"] == [
        {
            "status": "transcribed",
            "audio_kind": "audio",
            "source_kind": "asset",
            "selected_model": "source-stt:whisper-1",
            "transcript_length": 11,
        }
    ]
    assert "secret.example" not in str(metadata)
    assert "raw" not in str(metadata)


async def _prepare_speech_input(*args: Any, **kwargs: Any) -> Any:
    from apeiria.app.ai.runtime.speech import prepare_speech_input

    return await prepare_speech_input(*args, **kwargs)


def _turn(
    *,
    message_text: str,
    media_parts: tuple[RuntimeSourceMediaPart, ...],
) -> RuntimeTurnInput:
    return RuntimeTurnInput(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="onebot",
            bot_id="bot-1",
            scene_type="private",
            scene_id="user-1",
            subject_id="user-1",
        ),
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text=message_text,
            source_message_id="message-1",
            user_id="user-1",
            is_private=True,
            media_parts=media_parts,
        ),
        sender_id="bot-1",
    )


def _selected_stt() -> Any:
    return AISelectedCapabilityModel(
        capability_type="speech_to_text",
        source=AISourceDefinition(
            source_id="source-stt",
            name="STT Source",
            capability_type="speech_to_text",
            client_type="openai",
            preset_type="openai_compatible_stt",
            api_base="https://api.example.test/v1",
        ),
        model=AISpeechToTextModelDefinition(
            model_id="model-stt",
            source_id="source-stt",
            model_identifier="whisper-1",
            display_name="Whisper",
            capability_metadata={
                "lanes": ["speech_to_text"],
                "input_modalities": ["audio"],
                "output_modalities": ["text"],
            },
        ),
    )


@dataclass
class _ModelSelector:
    selected: Any

    async def select_stt_model(self) -> Any:
        return self.selected


@dataclass
class _AudioResolver:
    assets: dict[str, Path]

    def resolve_audio(self, media: RuntimeSourceMediaPart) -> Any:
        if media.asset_id and media.asset_id in self.assets:
            return SimpleNamespace(
                audio_bytes=self.assets[media.asset_id].read_bytes(),
                file_name=media.file_name or self.assets[media.asset_id].name,
                mime_type=media.mime_type or "application/octet-stream",
                source_kind="asset",
            )
        return None


@dataclass
class _Transcriber:
    outcome: str | BaseException

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def transcribe(self, **kwargs: Any) -> AIModelTranscriptionResponse:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return AIModelTranscriptionResponse(
            source_id=kwargs["source"].source_id,
            model_name=kwargs["model_name"],
            text=self.outcome,
        )
