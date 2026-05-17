"""Adapter contracts for AI model execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal, Protocol

from .normalization import sanitize_visible_reasoning

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass(frozen=True)
class AIModelToolDefinition:
    """One function-calling tool definition exposed to a model source adapter."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class AIModelToolCall:
    """One tool call returned by a model source adapter."""

    tool_call_id: str
    name: str
    arguments: dict[str, Any]


AIModelMessageRole = Literal["system", "user", "assistant", "tool"]
AIModelContentPartKind = Literal[
    "text",
    "image",
    "audio",
    "file",
    "tool_result",
    "provider_data",
]


@dataclass(frozen=True)
class AIModelContentPart:
    """One provider-neutral model-visible content part."""

    kind: AIModelContentPartKind
    text: str | None = None
    url: str | None = None
    mime_type: str | None = None
    data: bytes | None = None
    metadata: dict[str, Any] | None = None
    required: bool = True

    @classmethod
    def image(
        cls,
        *,
        url: str | None = None,
        data: bytes | None = None,
        mime_type: str | None = None,
        required: bool = True,
    ) -> "AIModelContentPart":
        return cls(
            kind="image",
            url=url,
            data=data,
            mime_type=mime_type,
            required=required,
        )


@dataclass(frozen=True)
class AIModelMessage:
    """One message in a chat conversation.

    - ``role="system"`` — system-level instructions (persona, rules).
    - ``role="user"`` — user turn.
    - ``role="assistant"`` — assistant turn, may carry ``tool_calls``.
    - ``role="tool"`` — tool result, must have ``tool_call_id``.
    """

    role: AIModelMessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple[AIModelToolCall, ...] = ()
    parts: tuple[AIModelContentPart, ...] = ()

    @property
    def text_content(self) -> str:
        """Return the text-compatible message content."""

        if self.content:
            return self.content
        text_parts = [part.text for part in self.parts if part.kind == "text"]
        return "\n".join(text for text in text_parts if isinstance(text, str))


@dataclass(frozen=True)
class AIModelCatalogItem:
    """One source-reported model catalog item."""

    id: str
    name: str
    capability_metadata: dict[str, Any] | None = None
    default_options: dict[str, Any] | None = None
    capability_provenance: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelGenerateRequest:
    """Unified text generation request for Apeiria AI services.

    When ``messages`` is non-empty, adapters use it directly (chat mode).
    When empty, ``prompt`` is wrapped as a single user message (plain-prompt mode).
    """

    source_id: str
    model_name: str
    prompt: str = ""
    messages: tuple[AIModelMessage, ...] = ()
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[AIModelToolDefinition, ...] = ()
    extra: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    degradations: tuple[Any, ...] = ()


@dataclass(frozen=True)
class AIModelGenerateResponse:
    """Unified text generation response for Apeiria AI services."""

    source_id: str
    model_name: str
    content: str
    tool_calls: tuple[AIModelToolCall, ...] = ()
    raw: dict[str, Any] | None = None
    parts: tuple[AIModelContentPart, ...] = ()
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    response_id: str | None = None
    reasoning_content: str | None = None
    reasoning_signature: str | None = None
    provider_data: dict[str, Any] | None = None

    @property
    def text_content(self) -> str:
        """Return the text-compatible response content."""

        if self.content:
            return self.content
        text_parts = [part.text for part in self.parts if part.kind == "text"]
        return "\n".join(text for text in text_parts if isinstance(text, str))

    def with_sanitized_visible_text(self) -> "AIModelGenerateResponse":
        """Return a copy with inline think-tag reasoning stripped from content."""

        sanitized = sanitize_visible_reasoning(self.content)
        if not sanitized.reasoning_stripped:
            return self
        provider_data = dict(self.provider_data or {})
        if sanitized.metadata:
            provider_data.update(sanitized.metadata)
        return replace(self, content=sanitized.text, provider_data=provider_data)


@dataclass(frozen=True)
class AIModelStreamRequest:
    """Unified text streaming generation request for model adapters."""

    source_id: str
    model_name: str
    prompt: str = ""
    messages: tuple[AIModelMessage, ...] = ()
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[AIModelToolDefinition, ...] = ()
    extra: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    degradations: tuple[Any, ...] = ()


AIModelStreamEventKind = Literal["start", "text_delta", "final", "failure"]


@dataclass(frozen=True)
class AIModelStreamEvent:
    """Provider-neutral lifecycle event for a text generation stream."""

    kind: AIModelStreamEventKind
    source_id: str
    model_name: str
    stream_id: str
    content_delta: str = ""
    response: AIModelGenerateResponse | None = None
    reason: str | None = None
    diagnostic: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def start(
        cls,
        *,
        source_id: str,
        model_name: str,
        stream_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> "AIModelStreamEvent":
        return cls(
            kind="start",
            source_id=source_id,
            model_name=model_name,
            stream_id=stream_id,
            metadata=metadata,
        )

    @classmethod
    def text_delta(
        cls,
        *,
        source_id: str,
        model_name: str,
        stream_id: str,
        content_delta: str,
        metadata: dict[str, Any] | None = None,
    ) -> "AIModelStreamEvent":
        return cls(
            kind="text_delta",
            source_id=source_id,
            model_name=model_name,
            stream_id=stream_id,
            content_delta=content_delta,
            metadata=metadata,
        )

    @classmethod
    def final(
        cls,
        *,
        source_id: str,
        model_name: str,
        stream_id: str,
        response: AIModelGenerateResponse,
        metadata: dict[str, Any] | None = None,
    ) -> "AIModelStreamEvent":
        return cls(
            kind="final",
            source_id=source_id,
            model_name=model_name,
            stream_id=stream_id,
            response=response,
            metadata=metadata,
        )

    @classmethod
    def failure(  # noqa: PLR0913
        cls,
        *,
        source_id: str,
        model_name: str,
        stream_id: str,
        reason: str,
        diagnostic: str,
        metadata: dict[str, Any] | None = None,
    ) -> "AIModelStreamEvent":
        return cls(
            kind="failure",
            source_id=source_id,
            model_name=model_name,
            stream_id=stream_id,
            reason=reason,
            diagnostic=diagnostic,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AIModelEmbeddingRequest:
    """Unified embedding request for Apeiria AI services."""

    source_id: str
    model_name: str
    texts: tuple[str, ...]
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelEmbeddingResponse:
    """Unified embedding response for Apeiria AI services."""

    source_id: str
    model_name: str
    vectors: tuple[tuple[float, ...], ...]
    raw: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelTranscriptionRequest:
    """Unified speech-to-text request for Apeiria AI services."""

    source_id: str
    model_name: str
    audio_bytes: bytes
    file_name: str = "sample.wav"
    mime_type: str = "audio/wav"
    language: str | None = None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelTranscriptionResponse:
    """Unified speech-to-text response for Apeiria AI services."""

    source_id: str
    model_name: str
    text: str
    raw: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelSpeechRequest:
    """Unified text-to-speech request for Apeiria AI services."""

    source_id: str
    model_name: str
    text: str
    voice: str = "alloy"
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "wav"
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelSpeechResponse:
    """Unified text-to-speech response for Apeiria AI services."""

    source_id: str
    model_name: str
    audio_bytes: bytes
    response_format: str
    raw: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelRerankResultItem:
    """One rerank-scored document result."""

    index: int
    relevance_score: float
    document: str | None = None


@dataclass(frozen=True)
class AIModelRerankRequest:
    """Unified rerank request for Apeiria AI services."""

    source_id: str
    model_name: str
    query: str
    documents: tuple[str, ...]
    top_n: int = 3
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIModelRerankResponse:
    """Unified rerank response for Apeiria AI services."""

    source_id: str
    model_name: str
    results: tuple[AIModelRerankResultItem, ...]
    raw: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None


class AIModelAdapter(Protocol):
    """Source adapter protocol for Apeiria model execution."""

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]: ...

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse: ...

    def stream_text(
        self,
        request: AIModelStreamRequest,
    ) -> AsyncIterator[AIModelStreamEvent]: ...

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse: ...

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse: ...

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse: ...

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse: ...
