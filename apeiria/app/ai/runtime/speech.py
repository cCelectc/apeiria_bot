"""Provider-neutral speech input preparation for live AI turns."""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from apeiria.ai.diagnostics import sanitize_runtime_diagnostic
from apeiria.ai.model.catalog.models import AISourceModelDefinition
from apeiria.ai.model.routing.models import AIModelProfileDefinition
from apeiria.ai.model.routing.selection import (
    AISelectedCapabilityModel,
    AISelectedModel,
)
from apeiria.ai.model.runtime.capabilities import (
    AIModelCapabilities,
    merge_model_capabilities,
    parse_model_capabilities,
)
from apeiria.app.ai.runtime.media import resolve_runtime_media_part

if TYPE_CHECKING:
    from apeiria.ai.config import AIPluginConfig
    from apeiria.ai.model.runtime.adapter import AIModelTranscriptionResponse
    from apeiria.app.ai.runtime.session.context import (
        RuntimeSourceMediaPart,
        RuntimeTurnInput,
    )

_DEFAULT_AUDIO_NAME = "audio-input"
_MAX_URL_AUDIO_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ResolvedSpeechAudio:
    """Bounded audio payload passed to provider-neutral STT calls."""

    audio_bytes: bytes
    file_name: str
    mime_type: str
    source_kind: str


@dataclass(frozen=True, slots=True)
class SpeechPreparationResult:
    """Prepared turn plus compact speech diagnostics."""

    turn: "RuntimeTurnInput"
    diagnostics: tuple[dict[str, object], ...] = ()


class SpeechAudioResolver(Protocol):
    """Resolve a safe runtime audio reference into bytes for STT."""

    def resolve_audio(
        self,
        media: "RuntimeSourceMediaPart",
    ) -> ResolvedSpeechAudio | None: ...


class SpeechModelSelector(Protocol):
    """Select a provider-neutral STT model."""

    async def select_stt_model(self) -> object | None: ...


class SpeechTranscriber(Protocol):
    """Invoke a selected STT model."""

    async def transcribe(
        self,
        **kwargs: object,
    ) -> "AIModelTranscriptionResponse | None": ...


class RuntimeSpeechInputPreparer:
    """Prepare enabled live speech input before normal turn stages."""

    def __init__(
        self,
        *,
        audio_resolver: SpeechAudioResolver | None = None,
        model_selector: SpeechModelSelector | None = None,
        transcriber: SpeechTranscriber | None = None,
    ) -> None:
        self._audio_resolver = audio_resolver or DefaultSpeechAudioResolver()
        self._model_selector = model_selector or DefaultSpeechModelSelector()
        self._transcriber = transcriber or ModelInvokerSpeechTranscriber()

    async def prepare(
        self,
        turn: "RuntimeTurnInput",
        *,
        config: "AIPluginConfig",
    ) -> SpeechPreparationResult:
        return await prepare_speech_input(
            turn,
            stt_input_enabled=config.stt_input_enabled,
            audio_resolver=self._audio_resolver,
            model_selector=self._model_selector,
            transcriber=self._transcriber,
        )


class DefaultSpeechAudioResolver:
    """Resolve only explicit safe audio references."""

    def resolve_audio(
        self,
        media: "RuntimeSourceMediaPart",
    ) -> ResolvedSpeechAudio | None:
        if media.url and _is_safe_http_url(media.url):
            try:
                with urllib.request.urlopen(media.url, timeout=10) as response:
                    data = response.read(_MAX_URL_AUDIO_BYTES + 1)
            except OSError:
                return None
            if not data or len(data) > _MAX_URL_AUDIO_BYTES:
                return None
            return ResolvedSpeechAudio(
                audio_bytes=data,
                file_name=media.file_name or _DEFAULT_AUDIO_NAME,
                mime_type=media.mime_type or "application/octet-stream",
                source_kind="url",
            )
        file_value = media.url or media.path_ref or media.file_ref
        if file_value:
            path = Path(file_value)
            if path.is_file():
                return ResolvedSpeechAudio(
                    audio_bytes=path.read_bytes(),
                    file_name=media.file_name or path.name,
                    mime_type=media.mime_type or "application/octet-stream",
                    source_kind="local_file",
                )
        part, _diagnostic = resolve_runtime_media_part(media)
        if part is not None and part.data:
            return ResolvedSpeechAudio(
                audio_bytes=part.data,
                file_name=_media_file_name(media),
                mime_type=part.mime_type
                or media.mime_type
                or "application/octet-stream",
                source_kind=_media_source_kind(part.metadata),
            )
        return None


class DefaultSpeechModelSelector:
    """Select the configured default speech-to-text capability model."""

    async def select_stt_model(self) -> object | None:
        from apeiria.ai.model.routing.capability_selection import (
            ai_model_capability_selection_service,
        )

        return await ai_model_capability_selection_service.select_default_model(
            capability_type="speech_to_text",
        )


class ModelInvokerSpeechTranscriber:
    """Adapter from speech preparation to the model invoker."""

    async def transcribe(
        self,
        **kwargs: object,
    ) -> "AIModelTranscriptionResponse | None":
        from apeiria.ai.model.runtime.service import model_invoker

        selected = kwargs["selected"]
        assert isinstance(selected, AISelectedModel)
        return await model_invoker.transcribe_audio(
            selected,
            audio_bytes=kwargs["audio_bytes"],  # type: ignore[arg-type]
            file_name=str(kwargs.get("file_name") or "sample.wav"),
            mime_type=str(kwargs.get("mime_type") or "audio/wav"),
        )


async def prepare_speech_input(  # noqa: PLR0911
    turn: "RuntimeTurnInput",
    *,
    stt_input_enabled: bool,
    audio_resolver: SpeechAudioResolver,
    model_selector: SpeechModelSelector,
    transcriber: SpeechTranscriber,
) -> SpeechPreparationResult:
    """Transcribe safe audio input into turn text when explicitly enabled."""

    audio_parts = tuple(
        part for part in turn.source.media_parts if part.kind == "audio"
    )
    if not audio_parts:
        return SpeechPreparationResult(turn=turn)

    if not stt_input_enabled:
        return SpeechPreparationResult(
            turn=turn,
            diagnostics=(
                {
                    "status": "disabled",
                    "reason": "stt_input_disabled",
                    "audio_count": len(audio_parts),
                },
            ),
        )

    selected = await model_selector.select_stt_model()
    if selected is None:
        return _with_diagnostics(
            turn,
            {
                "status": "speech_to_text_unavailable",
                "reason": "missing_stt_model",
                "audio_count": len(audio_parts),
            },
        )

    runtime_selected = _runtime_selected_model(selected)
    for audio in audio_parts:
        resolved = audio_resolver.resolve_audio(audio)
        if resolved is None:
            return _with_diagnostics(
                turn,
                {
                    "status": "unsupported_audio",
                    "reason": "unsafe_or_unresolved_audio",
                    "audio_kind": audio.kind,
                },
            )
        try:
            response = await transcriber.transcribe(
                selected=runtime_selected,
                source=runtime_selected.source,
                model_name=runtime_selected.resolved_model_name or "",
                audio_bytes=resolved.audio_bytes,
                file_name=resolved.file_name,
                mime_type=resolved.mime_type,
            )
        except Exception:  # noqa: BLE001
            return _with_diagnostics(
                turn,
                {
                    "status": "transcription_failed",
                    "reason": "provider_error",
                    "audio_kind": audio.kind,
                },
            )
        transcript = (getattr(response, "text", "") or "").strip()
        if not transcript:
            return _with_diagnostics(
                turn,
                {
                    "status": "empty_transcript",
                    "reason": "provider_returned_empty_transcript",
                    "audio_kind": audio.kind,
                },
            )
        diagnostics = {
            "status": "transcribed",
            "audio_kind": audio.kind,
            "source_kind": resolved.source_kind,
            "selected_model": _selected_model_ref(runtime_selected),
            "transcript_length": len(transcript),
        }
        remaining_media = tuple(
            media_part for media_part in turn.source.media_parts if media_part != audio
        )
        return _with_diagnostics(
            replace(
                turn,
                source=replace(
                    turn.source,
                    message_text=_compose_text(
                        typed_text=turn.message_text,
                        transcript=transcript,
                    ),
                    media_parts=remaining_media,
                ),
            ),
            diagnostics,
        )

    return SpeechPreparationResult(turn=turn)


def _runtime_selected_model(selected: object) -> AISelectedModel:
    if isinstance(selected, AISelectedModel):
        return selected
    assert isinstance(selected, AISelectedCapabilityModel)
    source = selected.source
    model = selected.model
    assert isinstance(model, AISourceModelDefinition)
    source_capabilities = parse_model_capabilities(source.capability_metadata)
    model_capabilities = parse_model_capabilities(model.capability_metadata)
    resolved_capabilities = merge_model_capabilities(
        merge_model_capabilities(source_capabilities, model_capabilities),
        _speech_lane_capabilities(getattr(selected, "capability_type", None)),
    )
    return AISelectedModel(
        source=source,
        source_model=model,
        profile=AIModelProfileDefinition(
            profile_id=f"capability_{model.model_id}",
            name=model.display_name or model.model_identifier,
            model_id=model.model_id,
            task_class="reply_default",
            priority=9999,
        ),
        resolved_model_name=model.model_identifier,
        resolved_capabilities=resolved_capabilities,
        model_default_options=dict(model.default_options or {}),
    )


def _speech_lane_capabilities(capability_type: object) -> AIModelCapabilities:
    if capability_type == "speech_to_text":
        return AIModelCapabilities(
            lanes=frozenset({"speech_to_text"}),
            input_modalities=frozenset({"audio"}),
            output_modalities=frozenset({"text"}),
            specified_fields=frozenset(
                {"lanes", "input_modalities", "output_modalities"}
            ),
        )
    return AIModelCapabilities()


def _compose_text(*, typed_text: str, transcript: str) -> str:
    typed = typed_text.strip()
    if not typed:
        return transcript
    return f"{typed}\n[transcribed speech] {transcript}"


def _media_file_name(media: "RuntimeSourceMediaPart") -> str:
    return media.file_name or media.file_ref or media.path_ref or _DEFAULT_AUDIO_NAME


def _media_source_kind(metadata: dict[str, Any] | None) -> str:
    if isinstance(metadata, dict):
        source_kind = metadata.get("source_kind")
        if isinstance(source_kind, str) and source_kind:
            return source_kind
    return "prepared_media"


def _with_diagnostics(
    turn: "RuntimeTurnInput",
    diagnostic: dict[str, object],
) -> SpeechPreparationResult:
    safe = _safe_speech_diagnostic(diagnostic)
    return SpeechPreparationResult(
        turn=replace(
            turn,
            source=replace(
                turn.source,
                speech_diagnostics=(*turn.source.speech_diagnostics, safe),
            ),
        ),
        diagnostics=(safe,),
    )


def _safe_speech_diagnostic(diagnostic: dict[str, object]) -> dict[str, object]:
    safe = sanitize_runtime_diagnostic(diagnostic)
    return cast("dict[str, object]", safe) if isinstance(safe, dict) else {}


def _selected_model_ref(selected: AISelectedModel) -> str:
    return f"{selected.source.source_id}:{selected.resolved_model_name or ''}"


def _is_safe_http_url(value: str) -> bool:
    return value.startswith(("https://", "http://"))


speech_input_preparer = RuntimeSpeechInputPreparer()

__all__ = [
    "DefaultSpeechAudioResolver",
    "ModelInvokerSpeechTranscriber",
    "ResolvedSpeechAudio",
    "RuntimeSpeechInputPreparer",
    "SpeechPreparationResult",
    "prepare_speech_input",
    "speech_input_preparer",
]
