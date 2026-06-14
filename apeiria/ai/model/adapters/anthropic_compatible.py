"""Anthropic-compatible source adapter."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from anthropic import AsyncAnthropic

from apeiria.ai.model.adapters._common import (
    _coerce_custom_headers,
    _coerce_float,
    _coerce_int,
    _coerce_str,
    _unsupported_part_text,
)
from apeiria.ai.model.runtime.adapter import (
    AIModelCatalogItem,
    AIModelEmbeddingRequest,
    AIModelEmbeddingResponse,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelMessage,
    AIModelRerankRequest,
    AIModelRerankResponse,
    AIModelSpeechRequest,
    AIModelSpeechResponse,
    AIModelStreamRequest,
    AIModelToolCall,
    AIModelTranscriptionRequest,
    AIModelTranscriptionResponse,
)
from apeiria.ai.model.runtime.capabilities import (
    AI_MODEL_REASONING_EFFORT_OPTION,
    AI_MODEL_REASONING_EFFORTS,
    normalize_reasoning_effort,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.model.runtime.adapter import AIModelStreamEvent


class AnthropicCompatibleProviderConfigError(RuntimeError):
    """Raised when required Anthropic-compatible settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"anthropic-compatible source requires {field_name}")


class AnthropicCompatibleProviderCapabilityError(RuntimeError):
    """Raised when Anthropic-compatible sources lack a requested capability."""

    def __init__(self) -> None:
        super().__init__("anthropic-compatible source does not support embeddings")


class AnthropicCompatibleProviderCapabilityActionError(RuntimeError):
    """Raised when Anthropic-compatible sources lack a requested capability."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"anthropic-compatible source does not support {capability}")


class AnthropicCompatibleProvider:
    """Anthropic-compatible text generation adapter backed by the official SDK."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        extra_config: dict[str, Any] | None = None,
        request_func: Any | None = None,
        list_request_func: Any | None = None,
    ) -> None:
        self.api_base = _normalize_anthropic_api_base(api_base)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.extra_config = extra_config or {}
        self._request_func = request_func
        self._list_request_func = list_request_func

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise AnthropicCompatibleProviderConfigError("api_base")
        if not api_key:
            raise AnthropicCompatibleProviderConfigError("api_key")

        system_text, chat_messages = _build_anthropic_payload(
            request.messages, request.prompt
        )
        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": chat_messages,
            "max_tokens": request.max_tokens or 1024,
        }
        planned_options = request.options or request.extra or {}
        max_tokens = request.max_tokens or _coerce_int(planned_options, "max_tokens")
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if system_text:
            payload["system"] = system_text
        temperature = request.temperature
        if temperature is None:
            temperature = _coerce_float(planned_options, "temperature")
        if temperature is not None:
            payload["temperature"] = temperature
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]
        reasoning_effort = normalize_reasoning_effort(
            planned_options.get(AI_MODEL_REASONING_EFFORT_OPTION)
        )
        if reasoning_effort is not None:
            payload["thinking"] = {"type": "adaptive"}
            payload["output_config"] = {"effort": reasoning_effort}

        client = AsyncAnthropic(
            api_key=api_key,
            base_url=api_base,
            timeout=self.timeout_seconds,
            max_retries=_coerce_int(self.extra_config, "max_retries") or 1,
            default_headers=_coerce_custom_headers(self.extra_config),
        )
        try:
            response = await client.messages.create(**payload)
        finally:
            await client.close()
        raw = response.model_dump(mode="json")
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_anthropic_content(response),
            tool_calls=tuple(_extract_anthropic_tool_calls(response)),
            raw=raw,
            usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else None,
            finish_reason=(
                str(raw.get("stop_reason")) if raw.get("stop_reason") else None
            ),
            response_id=str(raw.get("id")) if raw.get("id") is not None else None,
            reasoning_content=_extract_anthropic_reasoning_content(response),
            provider_data=_extract_anthropic_provider_data(raw),
        ).with_sanitized_visible_text()

    def stream_text(
        self,
        request: AIModelStreamRequest,
    ) -> "AsyncIterator[AIModelStreamEvent]":
        _ = request
        raise AnthropicCompatibleProviderCapabilityActionError("streaming")

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]:
        resolved_api_key = api_key or self.api_key
        if not self.api_base:
            raise AnthropicCompatibleProviderConfigError("api_base")
        if not resolved_api_key:
            raise AnthropicCompatibleProviderConfigError("api_key")

        client = AsyncAnthropic(
            api_key=resolved_api_key,
            base_url=self.api_base,
            timeout=self.timeout_seconds,
            max_retries=_coerce_int(self.extra_config, "max_retries") or 1,
            default_headers=_coerce_custom_headers(self.extra_config),
        )
        try:
            page = await client.models.list()
        finally:
            await client.close()
        return _extract_anthropic_models(page)

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse:
        _ = request
        raise AnthropicCompatibleProviderCapabilityError

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse:
        _ = request
        raise AnthropicCompatibleProviderCapabilityActionError("speech_to_text")

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse:
        _ = request
        raise AnthropicCompatibleProviderCapabilityActionError("text_to_speech")

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse:
        _ = request
        raise AnthropicCompatibleProviderCapabilityActionError("rerank")


def _normalize_anthropic_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


def _extract_anthropic_content(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def _extract_anthropic_models(page: Any) -> list[AIModelCatalogItem]:
    rows = getattr(page, "data", None)
    if not isinstance(rows, list):
        return []
    models: list[AIModelCatalogItem] = []
    for row in rows:
        model_id = getattr(row, "id", None)
        if not isinstance(model_id, str):
            continue
        display_name = getattr(row, "display_name", None)
        models.append(
            AIModelCatalogItem(
                id=model_id,
                name=display_name if isinstance(display_name, str) else model_id,
                capability_metadata=_extract_anthropic_model_capabilities(row),
            )
        )
    return models


def _extract_anthropic_model_capabilities(row: Any) -> dict[str, Any] | None:
    capabilities = getattr(row, "capabilities", None)
    if not isinstance(capabilities, dict):
        return None
    thinking = capabilities.get("thinking")
    effort = capabilities.get("effort")
    supports_thinking = isinstance(thinking, dict) and thinking.get("supported") is True
    efforts = _extract_supported_anthropic_efforts(effort)
    if not supports_thinking and not efforts:
        return None
    return {
        "reasoning": {
            "supported": supports_thinking or bool(efforts),
            "efforts": efforts,
        },
        "supported_options": [AI_MODEL_REASONING_EFFORT_OPTION],
    }


def _extract_supported_anthropic_efforts(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return []
    return [
        effort
        for effort in ("low", "medium", "high")
        if effort in AI_MODEL_REASONING_EFFORTS
        and isinstance(raw.get(effort), dict)
        and raw[effort].get("supported") is True
    ]


def _extract_anthropic_tool_calls(response: Any) -> list[AIModelToolCall]:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return []

    extracted: list[AIModelToolCall] = []
    for index, block in enumerate(content):
        if getattr(block, "type", None) != "tool_use":
            continue
        name = getattr(block, "name", None)
        if not isinstance(name, str) or not name.strip():
            continue
        input_payload = getattr(block, "input", None)
        extracted.append(
            AIModelToolCall(
                tool_call_id=str(getattr(block, "id", None) or f"tool_call_{index}"),
                name=name,
                arguments=input_payload if isinstance(input_payload, dict) else {},
            )
        )
    return extracted


def _extract_anthropic_reasoning_content(response: Any) -> str | None:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) in {"thinking", "redacted_thinking"}:
            text = getattr(block, "thinking", None) or getattr(block, "data", None)
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts) if parts else None


def _extract_anthropic_provider_data(raw: dict[str, Any]) -> dict[str, Any] | None:
    data = {
        key: raw[key]
        for key in ("stop_sequence", "model")
        if key in raw and raw[key] is not None
    }
    return data or None


def _build_anthropic_payload(
    messages: tuple[AIModelMessage, ...],
    fallback_prompt: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Convert ``AIModelMessage`` sequence to Anthropic API format.

    Returns ``(system_text, messages_list)``.  Anthropic requires:
    - ``system`` as a top-level parameter (not inside messages)
    - ``tool_result`` content blocks inside ``user`` messages
    - Messages must strictly alternate ``user`` / ``assistant``
    """

    if not messages:
        return "", [{"role": "user", "content": fallback_prompt}]

    system_parts: list[str] = []
    chat: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.text_content)
            continue

        if msg.role == "user":
            _append_anthropic_user(chat, _build_anthropic_user_content(msg))

        elif msg.role == "assistant":
            content: list[dict[str, Any]] = []
            if msg.text_content:
                content.append({"type": "text", "text": msg.text_content})
            content.extend(
                {
                    "type": "tool_use",
                    "id": tc.tool_call_id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
                for tc in msg.tool_calls
            )
            chat.append(
                {
                    "role": "assistant",
                    "content": content or [{"type": "text", "text": ""}],
                }
            )

        elif msg.role == "tool":
            # Anthropic requires tool_result inside a user message.
            tool_result_block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id or "",
                "content": msg.text_content,
            }
            # Merge into the last message if it's already a user message
            # with list content (i.e. another tool_result).
            if (
                chat
                and chat[-1]["role"] == "user"
                and isinstance(chat[-1]["content"], list)
            ):
                chat[-1]["content"].append(tool_result_block)
            else:
                chat.append(
                    {
                        "role": "user",
                        "content": [tool_result_block],
                    }
                )

    system_text = "\n\n".join(system_parts) if system_parts else ""
    return system_text, chat


def _append_anthropic_user(
    chat: list[dict[str, Any]],
    content: str | list[dict[str, Any]],
) -> None:
    """Append a user message, merging with the previous user message if needed.

    Anthropic requires strict user/assistant alternation.  Consecutive user
    messages (common in group chats) are merged into one.
    """

    if chat and chat[-1]["role"] == "user":
        prev = chat[-1]["content"]
        if isinstance(prev, str):
            if isinstance(content, str):
                chat[-1]["content"] = f"{prev}\n{content}"
            else:
                chat[-1]["content"] = [{"type": "text", "text": prev}, *content]
        elif isinstance(prev, list):
            if isinstance(content, str):
                prev.append({"type": "text", "text": content})
            else:
                prev.extend(content)
    else:
        chat.append({"role": "user", "content": content})


def _build_anthropic_user_content(
    msg: AIModelMessage,
) -> str | list[dict[str, Any]]:
    if not msg.parts:
        return msg.text_content

    blocks: list[dict[str, Any]] = []
    for part in msg.parts:
        if part.kind == "text" and part.text:
            blocks.append({"type": "text", "text": part.text})
        elif part.kind == "image" and part.data:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": part.mime_type or "image/png",
                        "data": base64.b64encode(part.data).decode("ascii"),
                    },
                }
            )
        elif part.kind == "image" and part.url:
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "url", "url": part.url},
                }
            )
        elif part.kind == "file" and part.data and _is_anthropic_document(part):
            blocks.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": part.mime_type or "application/pdf",
                        "data": base64.b64encode(part.data).decode("ascii"),
                    },
                }
            )
        elif part.kind in {"image", "audio", "file"}:
            blocks.append(
                {
                    "type": "text",
                    "text": _unsupported_part_text(part.kind),
                }
            )
    if blocks:
        return blocks
    return msg.text_content


def _is_anthropic_document(part: object) -> bool:
    mime_type = getattr(part, "mime_type", None)
    return mime_type in {"application/pdf", "text/plain", "text/markdown"}
