"""In-memory state container for WebChat sessions and history.

No file I/O — state is ephemeral (restart-safe via SQLite conversation
persistence). History replay on reconnect should query the async DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocol import MessageReceivePayload
    from .session import ChatSession


class WebChatStore:
    """Ephemeral container for active WebChat session state."""

    def load(
        self,
    ) -> tuple[dict[str, "ChatSession"], dict[str, list["MessageReceivePayload"]]]:
        return {}, {}

    def save(
        self,
        sessions: dict[str, "ChatSession"],
        history: dict[str, list["MessageReceivePayload"]],
    ) -> None:
        """No-op: state is ephemeral; sessions/messages are persisted in SQLite."""
