from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import apeiria.app.ai.future_tasks as future_tasks_package
import apeiria.app.ai.runtime.live as live_module
from apeiria.ai.config import AIPluginConfig
from apeiria.app.ai.reply_strategy import WakeContext
from apeiria.app.ai.runtime.live import DefaultAILiveRuntimeEntry
from apeiria.app.ai.runtime.stages import RuntimeCommitResult
from apeiria.conversation.models import ChatSessionIdentity


class _SessionRuntime:
    def __init__(self) -> None:
        self.recorded_keys: list[str | None] = []

    def record_event_if_new(self, key: str | None, **_: object) -> bool:
        self.recorded_keys.append(key)
        return True


class _Resolver:
    def __init__(self) -> None:
        self.runtime = _SessionRuntime()
        self.resolved_sessions: list[str] = []

    def resolve(self, session_id: str, **_: object) -> _SessionRuntime:
        self.resolved_sessions.append(session_id)
        return self.runtime


class _Engine:
    def __init__(
        self,
        *,
        reply_text: str,
        delivery_result: object | None = None,
    ) -> None:
        self.reply_text = reply_text
        self.delivery_result = delivery_result
        self.turn_modes: list[str] = []
        self.turns: list[object] = []

    async def run_reply_turn(self, **kwargs: object) -> RuntimeCommitResult:
        turn = kwargs["turn"]
        self.turn_modes.append(turn.runtime_mode)  # type: ignore[attr-defined]
        self.turns.append(turn)
        return RuntimeCommitResult(
            stage="commit",
            reply_text=self.reply_text,
            delivery_result=self.delivery_result,  # type: ignore[arg-type]
            commit_status="committed",
            substeps={"assistant_message": "committed"},
        )


def test_default_live_message_entry_uses_composed_defaults(
    monkeypatch: Any,
) -> None:
    resolver = _Resolver()
    engine = _Engine(reply_text="hello from composed engine")
    identity = _identity(scene_type="group")

    _patch_live_common(
        monkeypatch,
        resolver=resolver,
        engine=engine,
        identity=identity,
    )
    monkeypatch.setattr(
        live_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="hello",
            is_tome=True,
            is_private=False,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )

    reply = asyncio.run(
        DefaultAILiveRuntimeEntry().handle_message(
            SimpleNamespace(self_id="bot-1"),
            SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True),
        )
    )

    assert reply == "hello from composed engine"
    assert resolver.resolved_sessions == ["session-1"]
    assert resolver.runtime.recorded_keys == ["source_message:message-1"]
    assert engine.turn_modes == ["message"]


def test_default_live_message_entry_preserves_ingested_image_media(
    monkeypatch: Any,
) -> None:
    resolver = _Resolver()
    engine = _Engine(reply_text="image reply")
    identity = _identity(scene_type="private")

    _patch_live_common(
        monkeypatch,
        resolver=resolver,
        engine=engine,
        identity=identity,
        content_json=(
            '{"segments":[{"type":"text","text":"look"},'
            '{"type":"image","url":"https://cdn.example.test/cat.png",'
            '"mime":"image/png","alt":"a cat","token":"secret"}]}'
        ),
    )
    monkeypatch.setattr(
        live_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="look",
            is_tome=True,
            is_private=True,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )

    reply = asyncio.run(
        DefaultAILiveRuntimeEntry().handle_message(
            SimpleNamespace(self_id="bot-1"),
            SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True),
        )
    )

    assert reply == "image reply"
    turn = engine.turns[0]
    assert turn.source.media_parts[0].kind == "image"  # type: ignore[attr-defined]
    assert turn.source.media_parts[0].url == "https://cdn.example.test/cat.png"  # type: ignore[attr-defined]
    assert "secret" not in str(turn.source.media_parts)  # type: ignore[attr-defined]


def test_default_live_message_entry_skips_speech_when_disabled(
    monkeypatch: Any,
) -> None:
    resolver = _Resolver()
    engine = _Engine(reply_text="text reply")
    identity = _identity(scene_type="private")
    transcriber = _SpeechPreparerStub(transcript="ignored")

    _patch_live_common(
        monkeypatch,
        resolver=resolver,
        engine=engine,
        identity=identity,
        content_json=(
            '{"segments":[{"type":"record","asset_id":"asset-voice",'
            '"mime":"audio/ogg"}]}'
        ),
    )
    monkeypatch.setattr(
        live_module,
        "get_ai_plugin_config",
        lambda: AIPluginConfig(stt_input_enabled=False),
    )
    monkeypatch.setattr(live_module, "speech_input_preparer", transcriber)
    monkeypatch.setattr(
        live_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="[voice]",
            is_tome=True,
            is_private=True,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )

    reply = asyncio.run(
        DefaultAILiveRuntimeEntry().handle_message(
            SimpleNamespace(self_id="bot-1"),
            SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True),
        )
    )

    assert reply == "text reply"
    assert transcriber.calls == 0
    assert engine.turns[0].source.message_text == "[voice]"  # type: ignore[attr-defined]


def test_default_live_message_entry_threads_enabled_speech_transcript(
    monkeypatch: Any,
) -> None:
    resolver = _Resolver()
    engine = _Engine(reply_text="speech reply")
    identity = _identity(scene_type="private")
    transcriber = _SpeechPreparerStub(transcript="voice transcript")

    _patch_live_common(
        monkeypatch,
        resolver=resolver,
        engine=engine,
        identity=identity,
        content_json=(
            '{"segments":[{"type":"record","asset_id":"asset-voice",'
            '"mime":"audio/ogg"}]}'
        ),
    )
    monkeypatch.setattr(
        live_module,
        "get_ai_plugin_config",
        lambda: AIPluginConfig(stt_input_enabled=True),
    )
    monkeypatch.setattr(live_module, "speech_input_preparer", transcriber)
    monkeypatch.setattr(
        live_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="[voice]",
            is_tome=True,
            is_private=True,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )

    reply = asyncio.run(
        DefaultAILiveRuntimeEntry().handle_message(
            SimpleNamespace(self_id="bot-1"),
            SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True),
        )
    )

    assert reply == "speech reply"
    assert transcriber.calls == 1
    assert engine.turns[0].source.message_text == "voice transcript"  # type: ignore[attr-defined]


def test_default_live_message_entry_attaches_webchat_stream_sink(
    monkeypatch: Any,
) -> None:
    resolver = _Resolver()
    engine = _Engine(reply_text="streaming reply")
    identity = _identity(scene_type="private")
    sent_frames: list[tuple[str, object]] = []

    class WebChatBotStub:
        self_id = "webui_session-1"

        def __init__(self) -> None:
            self._connection = object()
            self._emitter = SimpleNamespace(
                emit_partial_reply_start=self._emit("reply.partial.start"),
                emit_partial_reply_delta=self._emit("reply.partial.delta"),
                emit_partial_reply_complete=self._emit("reply.partial.complete"),
                emit_partial_reply_failed=self._emit("reply.partial.failed"),
            )

        def _emit(self, type_: str) -> Any:
            async def emit(_connection: object, payload: object) -> None:
                sent_frames.append((type_, payload))

            return emit

    _patch_live_common(
        monkeypatch,
        resolver=resolver,
        engine=engine,
        identity=identity,
    )
    monkeypatch.setattr(
        live_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="webui_session-1",
            user_id="user-1",
            message_text="hello",
            is_tome=True,
            is_private=True,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )

    asyncio.run(
        DefaultAILiveRuntimeEntry().handle_message(
            WebChatBotStub(),
            SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True),
        )
    )
    sink = engine.turns[0].stream_sink  # type: ignore[attr-defined]
    asyncio.run(
        _publish_stream_events(
            sink,
            (
                SimpleNamespace(kind="start", stream_id="stream-1"),
                SimpleNamespace(
                    kind="text_delta",
                    stream_id="stream-1",
                    content_delta="hello",
                ),
            ),
        )
    )

    assert [frame[0] for frame in sent_frames] == [
        "reply.partial.start",
        "reply.partial.delta",
    ]
    assert sent_frames[1][1].content_delta == "hello"


async def _publish_stream_events(sink: Any, events: tuple[object, ...]) -> None:
    for event in events:
        sink(event)
    await asyncio.sleep(0)


def test_default_live_future_task_entry_maps_composed_commit_result(
    monkeypatch: Any,
) -> None:
    resolver = _Resolver()
    delivery_result = SimpleNamespace(
        delivered=False,
        reason="delivery_failed",
        error="adapter failed",
        status="failed",
        channel="onebot",
        remote_message_id=None,
    )
    engine = _Engine(reply_text="future reply", delivery_result=delivery_result)
    identity = _identity(scene_type="private")
    task = SimpleNamespace(
        task_id="task-1",
        session_id="session-1",
        status="running",
        description="remind me",
        source_message_id="message-1",
        user_id="user-1",
    )

    _patch_live_common(
        monkeypatch,
        resolver=resolver,
        engine=engine,
        identity=identity,
    )
    monkeypatch.setattr(
        future_tasks_package,
        "ai_future_task_service",
        SimpleNamespace(get_task=lambda **_kwargs: _async_value(task)),
    )

    result = asyncio.run(DefaultAILiveRuntimeEntry().handle_future_task("task-1"))

    assert result is not None
    assert result.reply_text == "future reply"
    assert result.commit_status == "committed"
    assert result.delivery_status == "failed"
    assert result.diagnostics["delivery_reason"] == "delivery_failed"
    assert resolver.resolved_sessions == ["session-1"]
    assert engine.turn_modes == ["future_task"]


def _patch_live_common(
    monkeypatch: Any,
    *,
    resolver: _Resolver,
    engine: _Engine,
    identity: ChatSessionIdentity,
    content_json: str | None = None,
) -> None:
    monkeypatch.setattr(
        live_module,
        "ensure_ai_runtime_support_initialized",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(live_module, "get_ai_plugin_config", AIPluginConfig)
    monkeypatch.setattr(
        live_module,
        "evaluate_wake",
        lambda _wake_context: SimpleNamespace(should_process=True),
    )
    monkeypatch.setattr(
        live_module,
        "ai_retention_service",
        SimpleNamespace(maybe_schedule_cleanup=lambda **_kwargs: None),
    )
    monkeypatch.setattr(
        live_module,
        "create_session_runtime_resolver",
        lambda: resolver,
    )
    monkeypatch.setattr(
        live_module,
        "create_session_turn_engine",
        lambda: engine,
    )
    monkeypatch.setattr(
        live_module,
        "store_extracted_memories",
        lambda **_kwargs: _async_value(SimpleNamespace(sentiment=None)),
    )
    monkeypatch.setattr(
        live_module,
        "chat_session_service",
        SimpleNamespace(
            ingest_event=lambda *_args, **_kwargs: _async_value(
                (
                    identity,
                    SimpleNamespace(
                        message_id="message-1",
                        platform_message_id=None,
                        content_json=content_json,
                    ),
                )
            ),
            get_session_identity=lambda **_kwargs: _async_value(identity),
        ),
    )


async def _async_value(value: object) -> object:
    return value


def _identity(*, scene_type: str) -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type=scene_type,  # type: ignore[arg-type]
        scene_id="scene-1",
        subject_id="user-1",
    )


class _SpeechPreparerStub:
    def __init__(self, *, transcript: str) -> None:
        self.transcript = transcript
        self.calls = 0

    async def prepare(self, turn: object, *, config: object) -> object:
        from dataclasses import replace

        assert config.stt_input_enabled is True
        self.calls += 1
        return SimpleNamespace(
            turn=replace(
                turn,
                source=replace(
                    turn.source,
                    message_text=self.transcript,
                ),
            ),
            diagnostics=(
                {
                    "status": "transcribed",
                    "audio_kind": "audio",
                    "source_kind": "asset",
                    "selected_model": "source-stt:whisper-1",
                    "transcript_length": len(self.transcript),
                },
            ),
        )
