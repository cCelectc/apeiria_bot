from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

OPENAI_INPUT_TOKENS = 10
OPENAI_OUTPUT_TOKENS = 5
OPENAI_TOTAL_TOKENS = 20
OPENAI_CACHED_TOKENS = 3
OPENAI_REASONING_TOKENS = 4
OPENAI_AUDIO_INPUT_TOKENS = 2
OPENAI_AUDIO_OUTPUT_TOKENS = 1
GEMINI_INPUT_TOKENS = 11
GEMINI_OUTPUT_TOKENS = 7
GEMINI_TOTAL_TOKENS = 18
GEMINI_CACHED_TOKENS = 4
GEMINI_REASONING_TOKENS = 3
OLLAMA_INPUT_TOKENS = 13
OLLAMA_OUTPUT_TOKENS = 8
OLLAMA_TOTAL_TOKENS = 21
ANTHROPIC_INPUT_TOKENS = 30
ANTHROPIC_OUTPUT_TOKENS = 12
ANTHROPIC_CACHED_TOTAL = 13
ANTHROPIC_TOTAL_TOKENS = 42
MEASURED_INPUT_TOKENS = 10
MEASURED_OUTPUT_TOKENS = 5
MEASURED_TOTAL_TOKENS = 15
EXPECTED_EVENT_COUNT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_openai_usage_normalization_preserves_details() -> None:
    from apeiria.ai.token_usage import normalize_provider_usage

    usage = normalize_provider_usage(
        adapter_kind="openai_compatible",
        usage={
            "prompt_tokens": OPENAI_INPUT_TOKENS,
            "completion_tokens": OPENAI_OUTPUT_TOKENS,
            "total_tokens": OPENAI_TOTAL_TOKENS,
            "prompt_tokens_details": {
                "cached_tokens": OPENAI_CACHED_TOKENS,
                "audio_tokens": OPENAI_AUDIO_INPUT_TOKENS,
            },
            "completion_tokens_details": {
                "reasoning_tokens": OPENAI_REASONING_TOKENS,
                "audio_tokens": OPENAI_AUDIO_OUTPUT_TOKENS,
            },
        },
    )

    assert usage.usage_available is True
    assert usage.measurement_source == "provider"
    assert usage.input_tokens == OPENAI_INPUT_TOKENS
    assert usage.output_tokens == OPENAI_OUTPUT_TOKENS
    assert usage.total_tokens == OPENAI_TOTAL_TOKENS
    assert usage.cached_input_tokens == OPENAI_CACHED_TOKENS
    assert usage.reasoning_tokens == OPENAI_REASONING_TOKENS
    assert usage.audio_input_tokens == OPENAI_AUDIO_INPUT_TOKENS
    assert usage.audio_output_tokens == OPENAI_AUDIO_OUTPUT_TOKENS
    assert usage.provider_usage == {
        "prompt_tokens": OPENAI_INPUT_TOKENS,
        "completion_tokens": OPENAI_OUTPUT_TOKENS,
        "total_tokens": OPENAI_TOTAL_TOKENS,
        "prompt_tokens_details": {
            "cached_tokens": OPENAI_CACHED_TOKENS,
            "audio_tokens": OPENAI_AUDIO_INPUT_TOKENS,
        },
        "completion_tokens_details": {
            "reasoning_tokens": OPENAI_REASONING_TOKENS,
            "audio_tokens": OPENAI_AUDIO_OUTPUT_TOKENS,
        },
    }


def test_missing_usage_normalization_does_not_estimate_tokens() -> None:
    from apeiria.ai.token_usage import normalize_provider_usage

    usage = normalize_provider_usage(
        adapter_kind="openai_compatible",
        usage=None,
    )

    assert usage.usage_available is False
    assert usage.measurement_source == "missing"
    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None
    assert usage.provider_usage is None


def test_gemini_and_ollama_usage_normalization() -> None:
    from apeiria.ai.token_usage import normalize_provider_usage

    gemini = normalize_provider_usage(
        adapter_kind="gemini_native",
        usage={
            "promptTokenCount": GEMINI_INPUT_TOKENS,
            "candidatesTokenCount": GEMINI_OUTPUT_TOKENS,
            "totalTokenCount": GEMINI_TOTAL_TOKENS,
            "cachedContentTokenCount": GEMINI_CACHED_TOKENS,
            "thoughtsTokenCount": GEMINI_REASONING_TOKENS,
        },
    )
    ollama = normalize_provider_usage(
        adapter_kind="ollama_native",
        usage={
            "prompt_eval_count": OLLAMA_INPUT_TOKENS,
            "eval_count": OLLAMA_OUTPUT_TOKENS,
        },
    )

    assert gemini.input_tokens == GEMINI_INPUT_TOKENS
    assert gemini.output_tokens == GEMINI_OUTPUT_TOKENS
    assert gemini.total_tokens == GEMINI_TOTAL_TOKENS
    assert gemini.cached_input_tokens == GEMINI_CACHED_TOKENS
    assert gemini.reasoning_tokens == GEMINI_REASONING_TOKENS
    assert ollama.input_tokens == OLLAMA_INPUT_TOKENS
    assert ollama.output_tokens == OLLAMA_OUTPUT_TOKENS
    assert ollama.total_tokens == OLLAMA_TOTAL_TOKENS


def test_anthropic_usage_normalization_combines_cache_tokens() -> None:
    from apeiria.ai.token_usage import normalize_provider_usage

    usage = normalize_provider_usage(
        adapter_kind="anthropic_compatible",
        usage={
            "input_tokens": ANTHROPIC_INPUT_TOKENS,
            "output_tokens": ANTHROPIC_OUTPUT_TOKENS,
            "cache_read_input_tokens": OLLAMA_OUTPUT_TOKENS,
            "cache_creation_input_tokens": OPENAI_OUTPUT_TOKENS,
        },
    )

    assert usage.input_tokens == ANTHROPIC_INPUT_TOKENS
    assert usage.output_tokens == ANTHROPIC_OUTPUT_TOKENS
    assert usage.total_tokens == ANTHROPIC_TOTAL_TOKENS
    assert usage.cached_input_tokens == ANTHROPIC_CACHED_TOTAL
    assert usage.provider_usage == {
        "input_tokens": ANTHROPIC_INPUT_TOKENS,
        "output_tokens": ANTHROPIC_OUTPUT_TOKENS,
        "cache_read_input_tokens": OLLAMA_OUTPUT_TOKENS,
        "cache_creation_input_tokens": OPENAI_OUTPUT_TOKENS,
    }


def test_invalid_token_values_are_not_normalized_as_totals() -> None:
    from apeiria.ai.token_usage import normalize_provider_usage

    usage = normalize_provider_usage(
        adapter_kind="openai_compatible",
        usage={
            "prompt_tokens": -1,
            "completion_tokens": True,
            "total_tokens": "15",
            "prompt_tokens_details": {"cached_tokens": -3},
            "completion_tokens_details": {"reasoning_tokens": object()},
        },
    )

    assert usage.usage_available is True
    assert usage.measurement_source == "provider"
    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None
    assert usage.cached_input_tokens is None
    assert usage.reasoning_tokens is None


def test_usage_repository_persists_and_aggregates_missing_usage(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.ai.token_usage import (
        AIModelUsageCreateInput,
        AIModelUsageRepository,
        normalize_provider_usage,
    )

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = AIModelUsageRepository()
    created_at = datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc)

    measured = repository.record_usage(
        AIModelUsageCreateInput(
            trace_id="trace-1",
            session_id="session-1",
            runtime_mode="message",
            response_source="direct",
            source_id="source-1",
            model_name="gpt-test",
            operation="chat_generation",
            attempt_index=1,
            status="success",
            provider_response_id="resp-1",
            finish_reason="stop",
            usage=normalize_provider_usage(
                adapter_kind="openai_compatible",
                usage={
                    "prompt_tokens": MEASURED_INPUT_TOKENS,
                    "completion_tokens": MEASURED_OUTPUT_TOKENS,
                    "total_tokens": MEASURED_TOTAL_TOKENS,
                },
            ),
            created_at=created_at,
        )
    )
    repository.record_usage(
        AIModelUsageCreateInput(
            trace_id="trace-2",
            session_id="session-1",
            runtime_mode="message",
            response_source="tool_loop",
            source_id="source-1",
            model_name="gpt-test",
            operation="chat_generation",
            attempt_index=2,
            status="empty_response",
            usage=normalize_provider_usage(
                adapter_kind="openai_compatible",
                usage=None,
            ),
            created_at=created_at,
        )
    )

    records = repository.list_usage_events(session_id="session-1", limit=10)
    summaries = repository.summarize_usage(group_by="session", session_id="session-1")
    windowed_records = repository.list_usage_events(
        session_id="session-1",
        limit=10,
        created_from=datetime(2026, 5, 17, 9, 59, tzinfo=timezone.utc),
        created_to=datetime(2026, 5, 17, 10, 1, tzinfo=timezone.utc),
    )
    empty_window = repository.list_usage_events(
        session_id="session-1",
        limit=10,
        created_from=datetime(2026, 5, 17, 10, 1, tzinfo=timezone.utc),
    )

    assert measured.input_tokens == MEASURED_INPUT_TOKENS
    assert [record.trace_id for record in records] == ["trace-2", "trace-1"]
    assert len(windowed_records) == EXPECTED_EVENT_COUNT
    assert empty_window == []
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.group_key == "session-1"
    assert summary.call_count == EXPECTED_EVENT_COUNT
    assert summary.measured_call_count == 1
    assert summary.missing_usage_count == 1
    assert summary.input_tokens == MEASURED_INPUT_TOKENS
    assert summary.output_tokens == MEASURED_OUTPUT_TOKENS
    assert summary.total_tokens == MEASURED_TOTAL_TOKENS
