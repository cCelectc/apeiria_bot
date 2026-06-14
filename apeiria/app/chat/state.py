"""State manager for WebChat sessions and message history."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from apeiria.i18n import t

from .protocol import (
    ChatSessionState,
    MessageReceivePayload,
    SessionCreatePayload,
    SessionDeletePayload,
    SessionSelectPayload,
    SessionStatus,
    WebUIPrincipal,
)
from .session import ChatSession
from .store import WebChatStore


class WebChatStateManager:
    """Own in-memory sessions/history — ephemeral, backed by SQLite for messages.

    This layer contains the canonical mutation rules for chat session state,
    including ownership checks, session reuse, history trimming.
    """

    def __init__(self, store: WebChatStore | None = None) -> None:
        self.store = store or WebChatStore()
        self._sessions, self._history = self.store.load()

    def create_session(
        self,
        principal: WebUIPrincipal,
        payload: SessionCreatePayload,
    ) -> ChatSessionState:
        """Create or resume a session for the same principal/target pair."""
        if session := self.find_session(principal.id, payload.target_user_id):
            session.status = SessionStatus.READY
            session.updated_at = datetime.now(timezone.utc)
            self.persist()
            return session.to_state()

        session = ChatSession.create(
            session_id=f"sess_{uuid4().hex}",
            created_by=principal,
            target_user_id=payload.target_user_id,
        )
        self._sessions[session.session_id] = session
        self._history[session.session_id] = []
        self.persist()
        return session.to_state()

    def select_session(
        self,
        principal: WebUIPrincipal,
        payload: SessionSelectPayload,
    ) -> ChatSessionState:
        session = self.get_session(payload.session_id)
        self.ensure_owner(session, principal)
        session.status = SessionStatus.READY
        session.updated_at = datetime.now(timezone.utc)
        self.persist()
        return session.to_state()

    def close_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.status = SessionStatus.CLOSED
        session.updated_at = datetime.now(timezone.utc)
        self.persist()

    def clear_history(
        self,
        session_id: str,
        principal: WebUIPrincipal,
    ) -> ChatSessionState:
        session = self.get_session(session_id)
        self.ensure_owner(session, principal)
        self._history[session_id] = []
        session.updated_at = datetime.now(timezone.utc)
        self.persist()
        return session.to_state()

    def delete_session(
        self,
        principal: WebUIPrincipal,
        payload: SessionDeletePayload,
    ) -> str:
        session = self.get_session(payload.session_id)
        self.ensure_owner(session, principal)
        self._sessions.pop(payload.session_id, None)
        self._history.pop(payload.session_id, None)
        self.persist()
        return payload.session_id

    def append_history(self, payload: MessageReceivePayload) -> None:
        """Append one message and trim persisted history to the latest 100 items."""
        self._history.setdefault(payload.session_id, []).append(payload)
        self._history[payload.session_id] = self._history[payload.session_id][-100:]
        self.persist()

    def get_history(self, session_id: str) -> list[MessageReceivePayload]:
        return self._history.get(session_id, [])

    def iter_sessions_for_principal(self, principal_id: str) -> list[ChatSession]:
        return [
            session
            for session in self._sessions.values()
            if session.created_by.id == principal_id
        ]

    def referenced_asset_ids(self) -> set[str]:
        """Collect asset ids still reachable from persisted chat history."""
        referenced: set[str] = set()
        for messages in self._history.values():
            for message in messages:
                for segment in message.segments:
                    asset_id = getattr(segment, "asset_id", None)
                    if isinstance(asset_id, str) and asset_id:
                        referenced.add(asset_id)
        return referenced

    def get_session(self, session_id: str) -> ChatSession:
        session = self._sessions.get(session_id)
        if session is None:
            from apeiria.app.chat.gateway import ChatSessionNotFoundError

            raise ChatSessionNotFoundError(t("web_ui.sessions.not_found"))
        return session

    def find_session(
        self,
        principal_id: str,
        target_user_id: str,
    ) -> ChatSession | None:
        candidates = [
            session
            for session in self._sessions.values()
            if session.created_by.id == principal_id
            and session.target_user_id == target_user_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda session: session.updated_at)

    def ensure_owner(self, session: ChatSession, principal: WebUIPrincipal) -> None:
        """Enforce that only the session creator can mutate that session."""
        if session.created_by.id != principal.id:
            from apeiria.app.chat.gateway import ChatSessionForbiddenError

            raise ChatSessionForbiddenError(t("web_ui.sessions.owner_mismatch"))

    def persist(self) -> None:
        """No-op: sessions/messages are persisted in SQLite conversation layer."""
