from __future__ import annotations

from typing import Any, cast


def test_build_ingested_chat_event_preserves_existing_message_mapping() -> None:
    from apeiria.conversation.ingest import build_ingested_chat_event

    class _Bot:
        type = "onebot"
        self_id = "bot-1"

    class _Event:
        group_id = "group-1"

        def get_user_id(self) -> str:
            return "user-1"

        def get_session_id(self) -> str:
            return "group_1_user-1"

        def get_plaintext(self) -> str:
            return "hello"

        def is_tome(self) -> bool:
            return True

        def get_message_id(self) -> int:
            return 42

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            assert mode == "json"
            return {
                "message_id": 42,
                "user_id": "user-1",
                "group_id": "group-1",
                "sender": {"nickname": "Alice"},
                "reply": {"message_id": 7, "text": "earlier"},
                "message": [
                    {"type": "at", "data": {"qq": "bot-1"}},
                    {"type": "image", "data": {"file": "img.png"}},
                ],
            }

    ingested = build_ingested_chat_event(
        cast("Any", _Bot()),
        cast("Any", _Event()),
        persist_raw_data=True,
    )

    assert ingested is not None
    assert ingested.identity.platform == "onebot"
    assert ingested.identity.bot_id == "bot-1"
    assert ingested.identity.scene_type == "group"
    assert ingested.identity.scene_id == "group-1"
    assert ingested.identity.subject_id is None
    assert ingested.author_id == "user-1"
    assert ingested.author_name == "Alice"
    assert ingested.platform_message_id == "42"
    assert ingested.platform_reply_id == "7"
    assert ingested.mentions_bot is True
    assert ingested.directed_to_bot is True
    assert ingested.has_media is True
    assert ingested.message_kind == "mixed"
    assert ingested.content == {
        "segments": [
            {"type": "text", "text": "hello"},
            {"type": "image", "file": "img.png"},
        ],
        "plain_text": "hello",
        "mentioned_user_ids": ["bot-1"],
        "quoted_text": "earlier",
    }
    assert ingested.raw_data == {
        "message_id": 42,
        "user_id": "user-1",
        "group_id": "group-1",
        "sender": {"nickname": "Alice"},
        "reply": {"message_id": 7, "text": "earlier"},
        "message_segment_types": ["at", "image"],
    }


def test_build_normalized_content_preserves_safe_media_references() -> None:
    from apeiria.conversation.normalization import build_normalized_content

    content = build_normalized_content(
        raw_data={
            "message": [
                {
                    "type": "image",
                    "data": {
                        "url": "https://cdn.example.test/cat.png",
                        "base64": "cG5n",
                        "file": "cat.png",
                        "mime": "image/png",
                        "alt": "a cat",
                        "raw": b"not-json-safe",
                        "token": "secret",
                    },
                },
                {
                    "type": "record",
                    "data": {
                        "url": "https://cdn.example.test/voice.ogg",
                        "mime": "audio/ogg",
                    },
                },
            ]
        },
        text_content="look at this",
    )

    assert content["segments"] == [
        {"type": "text", "text": "look at this"},
        {
            "type": "image",
            "url": "https://cdn.example.test/cat.png",
            "base64": "cG5n",
            "file": "cat.png",
            "mime": "image/png",
            "alt": "a cat",
        },
        {
            "type": "record",
            "url": "https://cdn.example.test/voice.ogg",
            "mime": "audio/ogg",
        },
    ]


def test_build_normalized_content_preserves_onebot_voice_audio_metadata() -> None:
    from apeiria.conversation.normalization import build_normalized_content

    content = build_normalized_content(
        raw_data={
            "message": [
                {
                    "type": "record",
                    "data": {
                        "file": "voice-1.silk",
                        "url": "https://cdn.example.test/voice-1.silk",
                        "mime": "audio/silk",
                        "duration": 3,
                        "size": 2048,
                        "token": "secret",
                        "raw": {"unsafe": True},
                    },
                },
                {
                    "type": "record",
                    "data": {"token": "secret"},
                },
            ]
        },
        text_content="",
        adapter="onebot",
    )

    assert content["segments"] == [
        {
            "type": "record",
            "url": "https://cdn.example.test/voice-1.silk",
            "file": "voice-1.silk",
            "mime": "audio/silk",
            "size": 2048,
            "duration": 3,
            "adapter": "onebot",
        },
        {
            "type": "record",
            "adapter": "onebot",
            "unsupported_reason": "missing_safe_reference",
        },
    ]
    assert "secret" not in str(content)
    assert "unsafe" not in str(content)


def test_build_normalized_content_preserves_platform_file_ids() -> None:
    from apeiria.app.ai.runtime.live import extract_runtime_media
    from apeiria.conversation.normalization import build_normalized_content

    content = build_normalized_content(
        raw_data={
            "message": [
                {
                    "type": "voice",
                    "data": {
                        "file_id": "voice-file-id",
                        "mime": "audio/ogg",
                    },
                },
                {
                    "type": "file",
                    "data": {
                        "file_id": "document-file-id",
                        "name": "doc.pdf",
                    },
                },
            ]
        },
        text_content="",
        adapter="onebot_v12",
    )

    assert content["segments"] == [
        {
            "type": "voice",
            "file_id": "voice-file-id",
            "platform_file_id": "voice-file-id",
            "mime": "audio/ogg",
            "adapter": "onebot_v12",
        },
        {
            "type": "file",
            "file_id": "document-file-id",
            "platform_file_id": "document-file-id",
            "name": "doc.pdf",
        },
    ]
    media = extract_runtime_media(__import__("json").dumps(content))
    assert [part.kind for part in media.parts] == ["audio", "file"]
    assert media.parts[0].file_ref == "voice-file-id"
    assert media.parts[1].file_ref == "document-file-id"


def test_adapter_specific_segments_are_preserved_as_safe_content() -> None:
    from apeiria.conversation.ingest import build_ingested_chat_event

    class _Bot:
        type = "onebot"
        self_id = "bot-1"

    class _Event:
        group_id = "group-1"

        def get_user_id(self) -> str:
            return "user-1"

        def get_session_id(self) -> str:
            return "group_1_user-1"

        def get_plaintext(self) -> str:
            return ""

        def is_tome(self) -> bool:
            return False

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            assert mode == "json"
            return {
                "message_id": "msg-1",
                "user_id": "user-1",
                "group_id": "group-1",
                "message": [
                    {
                        "type": "poke",
                        "data": {
                            "user_id": "user-2",
                            "target_id": "user-1",
                            "token": "secret",
                            "raw": {"nested": "not persisted"},
                        },
                    }
                ],
            }

    ingested = build_ingested_chat_event(
        cast("Any", _Bot()),
        cast("Any", _Event()),
    )

    assert ingested is not None
    assert ingested.message_kind == "text"
    assert ingested.content == {
        "segments": [
            {
                "type": "adapter",
                "adapter": "onebot",
                "segment_type": "poke",
                "data": {
                    "user_id": "user-2",
                    "target_id": "user-1",
                },
            }
        ],
        "plain_text": "",
        "mentioned_user_ids": [],
    }
