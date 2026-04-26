"""Persistence store for WebChat sessions and history."""

from __future__ import annotations

import json
from pathlib import Path

from nonebot.log import logger

from .protocol import ChatSessionState, MessageReceivePayload
from .session import ChatSession


class WebChatStore:
    def __init__(self) -> None:
        self._root = Path("data/web_ui/chat")
        self._root.mkdir(parents=True, exist_ok=True)
        self._state_file = self._root / "state.json"

    def load(
        self,
    ) -> tuple[dict[str, ChatSession], dict[str, list[MessageReceivePayload]]]:
        if not self._state_file.is_file():
            return {}, {}

        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load WebChat state from {}: {}",
                self._state_file,
                exc,
            )
            return {}, {}

        sessions = {
            item["session"]["session_id"]: ChatSession.from_state(
                ChatSessionState.model_validate(item["session"]),
            )
            for item in data.get("sessions", [])
            if item.get("session")
        }
        history = {
            item["session"]["session_id"]: [
                MessageReceivePayload.model_validate(message)
                for message in item.get("history", [])
            ]
            for item in data.get("sessions", [])
            if item.get("session")
        }
        return sessions, history

    def save(
        self,
        sessions: dict[str, ChatSession],
        history: dict[str, list[MessageReceivePayload]],
    ) -> None:
        payload = {
            "sessions": [
                {
                    "session": session.to_state().model_dump(mode="json"),
                    "history": [
                        message.model_dump(mode="json")
                        for message in history.get(session_id, [])
                    ],
                }
                for session_id, session in sorted(
                    sessions.items(),
                    key=lambda item: item[1].updated_at,
                )
            ],
        }
        temp_file = self._state_file.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(self._state_file)
