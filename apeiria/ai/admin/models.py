"""Model / source-model / profile / binding admin operations."""

from __future__ import annotations

import io
import re
import wave
from typing import TYPE_CHECKING, Literal, cast

from apeiria.ai.admin.audit import record_ai_admin_audit
from apeiria.ai.admin.errors import (
    AIAdminModelNotFoundError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from apeiria.ai.admin.sources import coerce_source_preset_type
from apeiria.ai.model.profile import (
    AIModelProfileCreateInput,
    ai_model_profile_service,
)
from apeiria.ai.model.source import ai_source_service
from apeiria.ai.model.sources import (
    AISourceCapabilityType,
    resolve_client_type_for_preset,
)

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelBindingSpec,
        AIModelCatalogItem,
        AIModelProfileDefinition,
        AISourceDefinition,
        AISourceModelDefinition,
    )
    from apeiria.ai.model.capability_registry import (
        AICapabilityModelRegistryEntry,
    )


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
) -> Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]:
    value = _coerce_optional_string(extra_config, key)
    if value in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
        return cast("Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm']", value)
    return "wav"


def _get_source_model_capability_fallback_order() -> tuple[
    "AISourceCapabilityType", ...
]:
    from apeiria.ai.model.capability_registry import (
        SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER,
    )

    return SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER


class ModelsAdminMixin:
    """Admin CRUD and test hooks for model profiles, bindings, and source models."""

    async def list_model_profiles(self) -> list["AIModelProfileDefinition"]:
        return await ai_model_profile_service.list_profiles()

    async def create_model_profile(  # noqa: PLR0913
        self,
        *,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        fallback_profile_id: str | None,
        actor_username: str | None = None,
    ) -> "AIModelProfileDefinition":
        create_input = await self._build_profile_create_input(
            name=name,
            model_id=model_id,
            task_class=task_class,
            priority=priority,
            enabled=enabled,
            fallback_profile_id=fallback_profile_id,
        )
        created = await ai_model_profile_service.create_profile(create_input)
        record_ai_admin_audit(
            "ai_model_profile_created",
            actor_username=actor_username,
            detail=f"{created.profile_id} {created.name}",
        )
        return created

    async def update_model_profile(  # noqa: PLR0913
        self,
        *,
        profile_id: str,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        fallback_profile_id: str | None,
        actor_username: str | None = None,
    ) -> "AIModelProfileDefinition | None":
        create_input = await self._build_profile_create_input(
            name=name,
            model_id=model_id,
            task_class=task_class,
            priority=priority,
            enabled=enabled,
            fallback_profile_id=fallback_profile_id,
        )
        updated = await ai_model_profile_service.update_profile(
            profile_id=profile_id,
            create_input=create_input,
        )
        if updated is not None:
            record_ai_admin_audit(
                "ai_model_profile_updated",
                actor_username=actor_username,
                detail=f"{updated.profile_id} {updated.name}",
            )
        return updated

    async def list_model_bindings(self) -> list["AIModelBindingSpec"]:
        return await ai_model_profile_service.list_bindings()

    async def list_source_models(
        self,
        *,
        source_id: str,
    ) -> list["AISourceModelDefinition"]:
        source = await ai_source_service.get_source(source_id=source_id)
        if source is None:
            return []
        return await self._list_managed_models(
            source=source,
            source_id=source_id,
        )

    async def fetch_source_models(  # noqa: PLR0913
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key_env_name: str | None = None,
        api_key: str | None = None,
        extra_config: dict[str, object] | None = None,
    ) -> list["AIModelCatalogItem"]:
        from apeiria.ai.model.service import ai_model_facade

        stored_source = None
        if source_id:
            sources = await ai_source_service.list_sources()
            stored_source = next(
                (item for item in sources if item.source_id == source_id),
            )
        source = self._resolve_source_for_model_fetch(
            stored_source=stored_source,
            preset_type=preset_type,
            api_base=api_base,
            api_key_env_name=api_key_env_name,
            extra_config=extra_config,
        )
        resolved_api_key = api_key or ai_source_service.get_source_api_key(source)
        if not resolved_api_key:
            raise AISourceModelFetchConfigError
        try:
            return await ai_model_facade.list_source_models(
                source=source,
                api_key=resolved_api_key,
            )
        except Exception as exc:
            raise AISourceModelFetchUpstreamError(
                _sanitize_upstream_error_detail(
                    exc,
                    secrets=(api_key, resolved_api_key),
                )
            ) from exc

    async def create_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        actor_username: str | None = None,
    ) -> "AISourceModelDefinition":
        source = await ai_source_service.get_source(source_id=source_id)
        if source is None:
            raise AIAdminModelNotFoundError
        created = await self._create_managed_model(
            source=source,
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        )
        record_ai_admin_audit(
            "ai_source_model_created",
            actor_username=actor_username,
            detail=f"{created.model_id} {created.display_name}",
        )
        return created

    async def update_source_model(  # noqa: PLR0913
        self,
        *,
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        actor_username: str | None = None,
    ) -> "AISourceModelDefinition | None":
        source = await ai_source_service.get_source(source_id=source_id)
        if source is None:
            return None
        updated = await self._update_managed_model(
            source=source,
            model_id=model_id,
            source_id=source_id,
            model_identifier=model_identifier,
            display_name=display_name,
            enabled=enabled,
            is_default=is_default,
            extra_params=extra_params,
        )
        if updated is not None:
            record_ai_admin_audit(
                "ai_source_model_updated",
                actor_username=actor_username,
                detail=f"{updated.model_id} {updated.display_name}",
            )
        return updated

    async def delete_source_model(
        self,
        *,
        model_id: str,
        source_id: str | None = None,
        actor_username: str | None = None,
    ) -> bool:
        capability_type = await self._resolve_model_capability_type(
            model_id=model_id,
            source_id=source_id,
        )
        existing_label = await self._build_source_model_audit_label(
            capability_type=capability_type,
            model_id=model_id,
        )
        dependent_profiles = await self._list_dependent_chat_model_profiles(
            capability_type=capability_type,
            model_id=model_id,
        )
        if dependent_profiles:
            labels = tuple(profile.name for profile in dependent_profiles[:3])
            raise AISourceModelDeleteBlockedError(
                profile_count=len(dependent_profiles),
                profile_labels=labels,
            )
        deleted = False
        if source_id:
            source = await ai_source_service.get_source(source_id=source_id)
            if source is not None:
                deleted = await self._delete_managed_model(
                    capability_type=source.capability_type,
                    model_id=model_id,
                )
            else:
                deleted = await self._delete_managed_model(
                    capability_type="chat_completion",
                    model_id=model_id,
                )
        if not deleted:
            for capability_type in _get_source_model_capability_fallback_order():
                deleted = await self._delete_managed_model(
                    capability_type=capability_type,
                    model_id=model_id,
                )
                if deleted:
                    break
        if deleted:
            record_ai_admin_audit(
                "ai_source_model_deleted",
                actor_username=actor_username,
                detail=existing_label,
            )
        return deleted

    async def _build_source_model_audit_label(
        self,
        *,
        capability_type: "AISourceCapabilityType | None",
        model_id: str,
    ) -> str:
        from apeiria.ai.model.chat_model import ai_chat_model_service

        if capability_type != "chat_completion":
            return model_id
        existing = await ai_chat_model_service.get_model(model_id=model_id)
        if existing is None:
            return model_id
        return f"{existing.model_id} {existing.display_name}"

    async def _list_dependent_chat_model_profiles(
        self,
        *,
        capability_type: "AISourceCapabilityType | None",
        model_id: str,
    ) -> list["AIModelProfileDefinition"]:
        if capability_type != "chat_completion":
            return []
        profiles = await ai_model_profile_service.list_profiles()
        return [profile for profile in profiles if profile.model_id == model_id]

    async def test_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key_env_name: str | None = None,
        api_key: str | None = None,
        extra_config: dict[str, object] | None = None,
        model_identifier: str,
    ) -> tuple[str, str, int]:
        from apeiria.ai.model.service import ai_model_facade

        resolved_model_identifier = model_identifier.strip()
        if not resolved_model_identifier:
            raise AISourceModelTestConfigError(
                AISourceModelTestConfigError.MISSING_MODEL_IDENTIFIER
            )

        stored_source = None
        if source_id:
            sources = await ai_source_service.list_sources()
            stored_source = next(
                (item for item in sources if item.source_id == source_id),
            )
        source = self._resolve_source_for_model_fetch(
            stored_source=stored_source,
            preset_type=preset_type,
            api_base=api_base,
            api_key_env_name=api_key_env_name,
            extra_config=extra_config,
        )
        resolved_api_key = api_key or ai_source_service.get_source_api_key(source)
        if not resolved_api_key:
            raise AISourceModelTestConfigError(
                AISourceModelFetchConfigError.MISSING_API_KEY
            )
        try:
            if source.capability_type == "embedding":
                embedding_response = await ai_model_facade.embed_texts_for_source(
                    source=source,
                    api_key=resolved_api_key,
                    model_name=resolved_model_identifier,
                    texts=(EMBEDDING_TEST_TEXT,),
                )
                dimensions = (
                    len(embedding_response.vectors[0])
                    if embedding_response.vectors
                    else 0
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
                    await ai_model_facade.transcribe_audio_for_source(
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
                speech_response = await ai_model_facade.synthesize_speech_for_source(
                    source=source,
                    api_key=resolved_api_key,
                    model_name=resolved_model_identifier,
                    text=TTS_TEST_TEXT,
                    voice=tts_voice,
                    response_format=tts_response_format,
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
                rerank_response = await ai_model_facade.rerank_documents_for_source(
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
            response = await ai_model_facade.generate_text_for_source(
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

    async def _build_profile_create_input(  # noqa: PLR0913
        self,
        *,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        fallback_profile_id: str | None,
    ) -> AIModelProfileCreateInput:
        if not model_id.strip():
            raise AIAdminModelNotFoundError
        return AIModelProfileCreateInput(
            name=name,
            model_id=model_id,
            task_class=task_class,  # type: ignore[arg-type]
            priority=priority,
            enabled=enabled,
            fallback_profile_id=fallback_profile_id,
        )

    @staticmethod
    def _resolve_source_for_model_fetch(
        *,
        stored_source: "AISourceDefinition | None",
        preset_type: str | None,
        api_base: str | None,
        api_key_env_name: str | None,
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

        effective_api_key_env_name = (
            api_key_env_name
            if api_key_env_name is not None
            else stored_source.api_key_env_name
            if stored_source
            else None
        )

        return ai_source_service.build_ephemeral_source(
            name=stored_source.name if stored_source is not None else "preview_source",
            capability_type=(  # type: ignore[arg-type]
                stored_source.capability_type
                if stored_source is not None
                else next(
                    (
                        item.capability_type
                        for item in ai_source_service.list_presets()
                        if item.preset_type == coerced_preset_type
                    ),
                    "chat_completion",
                )
            ),
            client_type=resolve_client_type_for_preset(coerced_preset_type),
            preset_type=coerced_preset_type,
            api_base=effective_api_base.strip(),
            api_key_env_name=(
                effective_api_key_env_name.strip()
                if isinstance(effective_api_key_env_name, str)
                and effective_api_key_env_name.strip()
                else None
            ),
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

    async def _create_managed_model(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
    ) -> "AISourceModelDefinition":
        entry = self._get_model_capability_entry(source.capability_type)
        return await entry.create_model(
            source_id,
            model_identifier,
            display_name,
            enabled,
            is_default,
            extra_params,
        )

    async def _update_managed_model(  # noqa: PLR0913
        self,
        *,
        source: "AISourceDefinition",
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
    ) -> "AISourceModelDefinition | None":
        entry = self._get_model_capability_entry(source.capability_type)
        return await entry.update_model(
            model_id,
            source_id,
            model_identifier,
            display_name,
            enabled,
            is_default,
            extra_params,
        )

    async def _list_managed_models(
        self,
        *,
        source: "AISourceDefinition",
        source_id: str,
    ) -> list["AISourceModelDefinition"]:
        entry = self._get_model_capability_entry(source.capability_type)
        return await entry.list_models(
            source_id,
        )

    async def _delete_managed_model(
        self,
        *,
        capability_type: "AISourceCapabilityType",
        model_id: str,
    ) -> bool:
        entry = self._get_model_capability_entry(capability_type)
        return await entry.delete_model(model_id)

    async def _resolve_model_capability_type(
        self,
        *,
        model_id: str,
        source_id: str | None = None,
    ) -> "AISourceCapabilityType | None":
        from apeiria.ai.model.chat_model import ai_chat_model_service
        from apeiria.ai.model.embedding_model import ai_embedding_model_service
        from apeiria.ai.model.rerank_model import ai_rerank_model_service
        from apeiria.ai.model.stt_model import ai_stt_model_service
        from apeiria.ai.model.tts_model import ai_tts_model_service

        if source_id:
            source = await ai_source_service.get_source(source_id=source_id)
            if source is not None:
                return source.capability_type

        lookups = (
            (
                cast("AISourceCapabilityType", "chat_completion"),
                ai_chat_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "embedding"),
                ai_embedding_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "speech_to_text"),
                ai_stt_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "text_to_speech"),
                ai_tts_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "rerank"),
                ai_rerank_model_service.get_model,
            ),
        )
        for capability_type, get_model in lookups:
            if await get_model(model_id=model_id) is not None:
                return cast("AISourceCapabilityType", capability_type)
        return None

    @staticmethod
    def _get_model_capability_entry(
        capability_type: "AISourceCapabilityType",
    ) -> "AICapabilityModelRegistryEntry":
        from apeiria.ai.model.capability_registry import (
            SOURCE_MODEL_CAPABILITY_REGISTRY,
        )

        return SOURCE_MODEL_CAPABILITY_REGISTRY[capability_type]


__all__ = ["ModelsAdminMixin"]
