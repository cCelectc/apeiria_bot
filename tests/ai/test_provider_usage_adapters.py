from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model.runtime.adapter import AIModelGenerateRequest

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_anthropic_generate_response_exposes_provider_usage(
    monkeypatch: MonkeyPatch,
) -> None:
    import apeiria.ai.model.adapters.anthropic_compatible as module
    from apeiria.ai.model.adapters.anthropic_compatible import (
        AnthropicCompatibleProvider,
    )

    usage = {
        "input_tokens": 23,
        "output_tokens": 7,
        "cache_read_input_tokens": 5,
        "cache_creation_input_tokens": 3,
    }

    class Messages:
        async def create(self, **_: Any) -> Any:
            return _AnthropicResponse(
                {
                    "id": "msg_1",
                    "content": [{"type": "text", "text": "hello"}],
                    "stop_reason": "end_turn",
                    "usage": usage,
                }
            )

    class Client:
        def __init__(self, **_: Any) -> None:
            self.messages = Messages()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "AsyncAnthropic", Client)
    provider = AnthropicCompatibleProvider(
        api_base="https://example.invalid",
        api_key="test-key",
    )

    response = asyncio.run(provider.generate_text(_generate_request("claude-test")))

    assert response.content == "hello"
    assert response.finish_reason == "end_turn"
    assert response.response_id == "msg_1"
    assert response.usage == usage
    assert response.raw is not None
    assert response.raw["usage"] == usage


def test_gemini_generate_response_exposes_usage_metadata() -> None:
    from apeiria.ai.model.adapters.gemini_native import GeminiNativeProvider

    usage = {
        "promptTokenCount": 19,
        "candidatesTokenCount": 11,
        "totalTokenCount": 30,
        "cachedContentTokenCount": 4,
        "thoughtsTokenCount": 2,
    }
    payload = {
        "responseId": "gemini-response-1",
        "modelVersion": "gemini-test-001",
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": "gemini response"}]},
            }
        ],
        "usageMetadata": usage,
    }
    provider = GeminiNativeProvider(
        api_base="https://example.invalid/v1beta",
        api_key="test-key",
        request_func=_json_response(payload),
    )

    response = asyncio.run(provider.generate_text(_generate_request("gemini-test")))

    assert response.content == "gemini response"
    assert response.finish_reason == "STOP"
    assert response.response_id == "gemini-response-1"
    assert response.usage == usage
    assert response.raw == payload


def test_ollama_generate_response_exposes_native_usage_counts() -> None:
    from apeiria.ai.model.adapters.ollama_native import OllamaNativeProvider

    payload = {
        "message": {"role": "assistant", "content": "ollama response"},
        "done_reason": "stop",
        "prompt_eval_count": 13,
        "eval_count": 8,
        "prompt_eval_duration": 1200,
        "eval_duration": 3400,
        "load_duration": 500,
        "total_duration": 5100,
    }
    provider = OllamaNativeProvider(
        api_base="http://localhost:11434",
        request_func=_json_response(payload),
    )

    response = asyncio.run(provider.generate_text(_generate_request("llama-test")))

    assert response.content == "ollama response"
    assert response.finish_reason == "stop"
    assert response.usage == {
        "prompt_eval_count": 13,
        "eval_count": 8,
        "total_duration": 5100,
        "load_duration": 500,
        "prompt_eval_duration": 1200,
        "eval_duration": 3400,
    }
    assert response.raw == payload


def test_openai_embedding_response_exposes_provider_usage(
    monkeypatch: MonkeyPatch,
) -> None:
    import apeiria.ai.model.adapters.openai_compatible as module
    from apeiria.ai.model.adapters.openai_compatible import OpenAICompatibleProvider
    from apeiria.ai.model.runtime.adapter import AIModelEmbeddingRequest

    usage = {"prompt_tokens": 6, "total_tokens": 6}

    class Embeddings:
        async def create(self, **_: Any) -> Any:
            return _OpenAIResponse(
                {
                    "data": [{"embedding": [0.1, 0.2]}],
                    "usage": usage,
                }
            )

    class Client:
        def __init__(self) -> None:
            self.embeddings = Embeddings()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "_build_openai_client", lambda **_: Client())
    provider = OpenAICompatibleProvider(
        api_base="https://example.invalid/v1",
        api_key="test-key",
    )

    response = asyncio.run(
        provider.embed_texts(
            AIModelEmbeddingRequest(
                source_id="source-1",
                model_name="embedding-test",
                texts=("hello",),
            )
        )
    )

    assert response.vectors == ((0.1, 0.2),)
    assert response.usage == usage


def test_gemini_embedding_response_exposes_usage_metadata() -> None:
    from apeiria.ai.model.adapters.gemini_native import GeminiNativeProvider
    from apeiria.ai.model.runtime.adapter import AIModelEmbeddingRequest

    usage = {"promptTokenCount": 4, "totalTokenCount": 4}
    payload = {
        "embedding": {"values": [0.3, 0.4]},
        "usageMetadata": usage,
    }
    provider = GeminiNativeProvider(
        api_base="https://example.invalid/v1beta",
        api_key="test-key",
        request_func=_json_response(payload),
    )

    response = asyncio.run(
        provider.embed_texts(
            AIModelEmbeddingRequest(
                source_id="source-1",
                model_name="gemini-embedding-test",
                texts=("hello",),
            )
        )
    )

    assert response.vectors == ((0.3, 0.4),)
    assert response.usage == usage


def test_ollama_embedding_response_exposes_native_usage_counts() -> None:
    from apeiria.ai.model.adapters.ollama_native import OllamaNativeProvider
    from apeiria.ai.model.runtime.adapter import AIModelEmbeddingRequest

    payload = {
        "embedding": [0.5, 0.6],
        "prompt_eval_count": 9,
        "total_duration": 1200,
    }
    provider = OllamaNativeProvider(
        api_base="http://localhost:11434",
        request_func=_json_response(payload),
    )

    response = asyncio.run(
        provider.embed_texts(
            AIModelEmbeddingRequest(
                source_id="source-1",
                model_name="nomic-embed-test",
                texts=("hello",),
            )
        )
    )

    assert response.vectors == ((0.5, 0.6),)
    assert response.usage == {
        "prompt_eval_count": 9,
        "total_duration": 1200,
    }


def test_generic_rerank_response_exposes_provider_usage() -> None:
    from apeiria.ai.model.adapters.generic_rerank import GenericRerankProvider
    from apeiria.ai.model.runtime.adapter import AIModelRerankRequest

    usage = {"prompt_tokens": 14, "total_tokens": 14}
    payload = {
        "results": [{"index": 0, "relevance_score": 0.91}],
        "usage": usage,
    }
    provider = GenericRerankProvider(
        api_base="https://example.invalid",
        api_key="test-key",
        request_func=_http_response(payload),
    )

    response = asyncio.run(
        provider.rerank_documents(
            AIModelRerankRequest(
                source_id="source-1",
                model_name="rerank-test",
                query="hello",
                documents=("hello world", "bye"),
            )
        )
    )

    assert response.results[0].document == "hello world"
    assert response.usage == usage


def _generate_request(model_name: str) -> AIModelGenerateRequest:
    return AIModelGenerateRequest(
        source_id="source-1",
        model_name=model_name,
        prompt="hello",
    )


def _json_response(payload: dict[str, Any]) -> Any:
    async def request(_: Any) -> SimpleNamespace:
        return SimpleNamespace(json=lambda: payload)

    return request


class _AnthropicResponse:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.content = [
            SimpleNamespace(**block)
            for block in raw.get("content", [])
            if isinstance(block, dict)
        ]

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self._raw


class _OpenAIResponse:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.data = [
            SimpleNamespace(**item)
            for item in raw.get("data", [])
            if isinstance(item, dict)
        ]

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self._raw


class _HTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.status_code = 200

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _http_response(payload: dict[str, Any]) -> Any:
    async def request(*_: Any, **__: Any) -> _HTTPResponse:
        return _HTTPResponse(payload)

    return request
