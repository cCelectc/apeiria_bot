"""Source-model catalog and connectivity checks for AI admin."""

from __future__ import annotations

import io
import re
import wave
from typing import TYPE_CHECKING, cast

from apeiria.ai.model import resolve_client_type_for_preset
from apeiria.ai.model.catalog.capability_templates import enrich_catalog_item
from apeiria.ai.model.runtime.adapter import AIModelCatalogItem
from apeiria.ai.model.runtime.capability_sources import (
    capability_provenance_to_metadata,
)
from apeiria.app.ai.operations.errors import (
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from apeiria.app.ai.operations.sources import coerce_source_preset_type
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from typing import Literal

    from apeiria.ai.model import AISourceDefinition


MODEL_TEST_PROMPT = "Reply with exactly OK."
EMBEDDING_TEST_TEXT = "Apeiria embedding connectivity check"
TTS_TEST_TEXT = "Apeiria text to speech connectivity check"
RERANK_TEST_QUERY = "Which sentence is about connectivity?"
RERANK_TEST_DOCUMENTS = (
    "This document is unrelated to the task.",
    "This sentence is about connectivity verification.",
    "Another unrelated document.",
)

_REDACTED_TOKEN_TEXT = "[redacted]"
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]+)")
_AUTH_HEADER_PATTERN = re.compile(
    r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?bearer\s+)([A-Za-z0-9._~+/=-]+)"
)


async def fetch_source_model_catalog(
    *,
    source_id: str | None = None,
    preset_type: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    extra_config: dict[str, object] | None = None,
) -> list["AIModelCatalogItem"]:
    stored_source = None
    if source_id:
        stored_source = await ai_wiring.model.source_service.get_source(
            source_id=source_id
        )
    source = _resolve_source_for_model_fetch(
        stored_source=stored_source,
        preset_type=preset_type,
        api_base=api_base,
        extra_config=extra_config,
    )
    resolved_api_key = (
        api_key
        or _stored_source_api_key(stored_source)
        or ai_wiring.model.source_service.get_source_api_key(source)
    )
    if not resolved_api_key:
        raise AISourceModelFetchConfigError
    try:
        catalog_items = await ai_wiring.model.invoker.list_source_models(
            source=source,
            api_key=resolved_api_key,
        )
        return [
            _enrich_catalog_item(source=source, item=item) for item in catalog_items
        ]
    except Exception as exc:
        raise AISourceModelFetchUpstreamError(
            _sanitize_upstream_error_detail(
                exc,
                secrets=(api_key, resolved_api_key),
            )
        ) from exc


def _enrich_catalog_item(
    *,
    source: "AISourceDefinition",
    item: "AIModelCatalogItem",
) -> "AIModelCatalogItem":
    enrichment = enrich_catalog_item(source=source, catalog_item=item)
    return AIModelCatalogItem(
        id=item.id,
        name=item.name,
        capability_metadata=enrichment.capability_metadata,
        default_options=enrichment.default_options,
        capability_provenance=capability_provenance_to_metadata(enrichment.provenance),
    )


async def test_source_model_connectivity(  # noqa: PLR0913
    *,
    source_id: str | None = None,
    preset_type: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    extra_config: dict[str, object] | None = None,
    model_identifier: str,
) -> tuple[str, str, int]:
    resolved_model_identifier = model_identifier.strip()
    if not resolved_model_identifier:
        raise AISourceModelTestConfigError(
            AISourceModelTestConfigError.MISSING_MODEL_IDENTIFIER
        )

    stored_source = None
    if source_id:
        stored_source = await ai_wiring.model.source_service.get_source(
            source_id=source_id
        )
    source = _resolve_source_for_model_fetch(
        stored_source=stored_source,
        preset_type=preset_type,
        api_base=api_base,
        extra_config=extra_config,
    )
    resolved_api_key = (
        api_key
        or _stored_source_api_key(stored_source)
        or ai_wiring.model.source_service.get_source_api_key(source)
    )
    if not resolved_api_key:
        raise AISourceModelTestConfigError(
            AISourceModelFetchConfigError.MISSING_API_KEY
        )
    try:
        if source.capability_type == "embedding":
            embedding_response = await ai_wiring.model.invoker.embed_texts_for_source(
                source=source,
                api_key=resolved_api_key,
                model_name=resolved_model_identifier,
                texts=(EMBEDDING_TEST_TEXT,),
            )
            dimensions = (
                len(embedding_response.vectors[0]) if embedding_response.vectors else 0
            )
            embedding_summary = (
                f"{len(embedding_response.vectors)} vector, {dimensions} dims"
            )
            return (
                resolved_model_identifier,
                f"embedding ok ({embedding_summary})",
                0,
            )
        if source.capability_type == "speech_to_text":
            stt_language = _coerce_optional_string(
                source.extra_config,
                "stt_language",
            )
            transcription_response = (
                await ai_wiring.model.invoker.transcribe_audio_for_source(
                    source=source,
                    api_key=resolved_api_key,
                    model_name=resolved_model_identifier,
                    audio_bytes=_build_test_wav_bytes(),
                    language=stt_language,
                )
            )
            transcription_summary = transcription_response.text.strip()
            return (
                resolved_model_identifier,
                (
                    f"stt ok: {transcription_summary}"
                    if transcription_summary
                    else "stt ok (empty transcript)"
                ),
                0,
            )
        if source.capability_type == "text_to_speech":
            tts_voice = (
                _coerce_optional_string(source.extra_config, "tts_voice") or "alloy"
            )
            tts_response_format = _coerce_response_format(
                source.extra_config,
                "tts_response_format",
            )
            speech_response = (
                await ai_wiring.model.invoker.synthesize_speech_for_source(
                    source=source,
                    api_key=resolved_api_key,
                    model_name=resolved_model_identifier,
                    text=TTS_TEST_TEXT,
                    voice=tts_voice,
                    response_format=tts_response_format,
                )
            )
            return (
                resolved_model_identifier,
                f"tts ok ({len(speech_response.audio_bytes)} bytes)",
                0,
            )
        if source.capability_type == "rerank":
            rerank_top_n = (
                _coerce_optional_int(source.extra_config, "rerank_top_n") or 2
            )
            rerank_response = await ai_wiring.model.invoker.rerank_documents_for_source(
                source=source,
                api_key=resolved_api_key,
                model_name=resolved_model_identifier,
                query=RERANK_TEST_QUERY,
                documents=RERANK_TEST_DOCUMENTS,
                top_n=rerank_top_n,
            )
            top_score = (
                rerank_response.results[0].relevance_score
                if rerank_response.results
                else 0.0
            )
            rerank_summary = (
                f"{len(rerank_response.results)} results, top={top_score:.3f}"
            )
            return (
                resolved_model_identifier,
                f"rerank ok ({rerank_summary})",
                0,
            )
        response = await ai_wiring.model.invoker.generate_text_for_source(
            source=source,
            api_key=resolved_api_key,
            model_name=resolved_model_identifier,
            prompt=MODEL_TEST_PROMPT,
            max_tokens=32,
        )
    except Exception as exc:
        raise AISourceModelTestUpstreamError(
            _sanitize_upstream_error_detail(
                exc,
                secrets=(api_key, resolved_api_key),
            )
        ) from exc
    return (
        resolved_model_identifier,
        response.content.strip(),
        len(response.tool_calls),
    )


def _resolve_source_for_model_fetch(
    *,
    stored_source: "AISourceDefinition | None",
    preset_type: str | None,
    api_base: str | None,
    extra_config: dict[str, object] | None = None,
) -> "AISourceDefinition":
    effective_preset_type = preset_type or (
        stored_source.preset_type if stored_source is not None else None
    )
    if not effective_preset_type:
        raise AISourceModelFetchConfigError(
            AISourceModelFetchConfigError.MISSING_PRESET
        )

    coerced_preset_type = coerce_source_preset_type(effective_preset_type)
    effective_api_base = (
        api_base
        if api_base is not None
        else stored_source.api_base
        if stored_source
        else None
    )
    if not effective_api_base or not effective_api_base.strip():
        raise AISourceModelFetchConfigError(
            AISourceModelFetchConfigError.MISSING_API_BASE
        )

    return ai_wiring.model.source_service.build_ephemeral_source(
        name=stored_source.name if stored_source is not None else "preview_source",
        capability_type=(  # type: ignore[arg-type]
            stored_source.capability_type
            if stored_source is not None
            else next(
                (
                    item.capability_type
                    for item in ai_wiring.model.source_service.list_presets()
                    if item.preset_type == coerced_preset_type
                ),
                "chat_completion",
            )
        ),
        client_type=resolve_client_type_for_preset(coerced_preset_type),
        preset_type=coerced_preset_type,
        api_base=effective_api_base.strip(),
        enabled=stored_source.enabled if stored_source is not None else True,
        timeout_seconds=(
            stored_source.timeout_seconds if stored_source is not None else None
        ),
        custom_headers=(
            stored_source.custom_headers if stored_source is not None else None
        ),
        extra_config=(
            extra_config
            if extra_config is not None
            else stored_source.extra_config
            if stored_source is not None
            else None
        ),
    )


def _stored_source_api_key(source: "AISourceDefinition | None") -> str | None:
    if source is None:
        return None
    return ai_wiring.model.source_service.get_source_api_key(source)


def _sanitize_upstream_error_detail(
    detail: object,
    *,
    secrets: tuple[str | None, ...] = (),
) -> str:
    """Remove obvious credential material from upstream error text."""

    text = str(detail).strip()
    if not text:
        return "upstream request failed"

    sanitized = _BEARER_TOKEN_PATTERN.sub(
        rf"\1{_REDACTED_TOKEN_TEXT}",
        text,
    )
    sanitized = _AUTH_HEADER_PATTERN.sub(
        rf"\1{_REDACTED_TOKEN_TEXT}",
        sanitized,
    )

    for secret in secrets:
        if not isinstance(secret, str):
            continue
        normalized = secret.strip()
        if not normalized:
            continue
        sanitized = sanitized.replace(normalized, _REDACTED_TOKEN_TEXT)

    return sanitized or "upstream request failed"


def _build_test_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 16000)
    return buffer.getvalue()


def _coerce_optional_string(
    extra_config: dict[str, object] | None,
    key: str,
) -> str | None:
    if not extra_config:
        return None
    value = extra_config.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _coerce_optional_int(
    extra_config: dict[str, object] | None,
    key: str,
) -> int | None:
    if not extra_config:
        return None
    value = extra_config.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _coerce_response_format(
    extra_config: dict[str, object] | None,
    key: str,
) -> "Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm']":
    value = _coerce_optional_string(extra_config, key)
    if value in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
        return cast("Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm']", value)
    return "wav"
