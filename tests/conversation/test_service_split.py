from __future__ import annotations

import importlib
import sys
from typing import Any, cast


def test_conversation_ingest_and_normalization_modules_exist() -> None:
    for module_name in (
        "apeiria.conversation.ingest",
        "apeiria.conversation.normalization",
    ):
        sys.modules.pop(module_name, None)

    ingest_module = importlib.import_module("apeiria.conversation.ingest")
    normalization_module = importlib.import_module(
        "apeiria.conversation.normalization"
    )

    assert hasattr(ingest_module, "build_ingested_chat_event")
    assert hasattr(normalization_module, "build_normalized_content")
    assert hasattr(normalization_module, "build_debug_raw_payload")


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
            {"type": "image"},
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
