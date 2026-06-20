"""Session models for WebChat."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .protocol import ChatSessionState, SessionStatus, WebUIPrincipal


@dataclass
class ChatSession:
    session_id: str
    created_by: WebUIPrincipal
    target_user_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        created_by: WebUIPrincipal,
        target_user_id: str,
    ) -> "ChatSession":
        now = datetime.now(timezone.utc)
        return cls(
            session_id=session_id,
            created_by=created_by,
            target_user_id=target_user_id,
            status=SessionStatus.READY,
            created_at=now,
            updated_at=now,
        )

    def to_state(self) -> ChatSessionState:
        return ChatSessionState(
            session_id=self.session_id,
            status=self.status,
            target_user_id=self.target_user_id,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_state(cls, state: ChatSessionState) -> "ChatSession":
        return cls(
            session_id=state.session_id,
            created_by=state.created_by
            or WebUIPrincipal(id="webui", username="webui", role="admin"),
            target_user_id=state.target_user_id,
            status=state.status,
            created_at=state.created_at or datetime.now(timezone.utc),
            updated_at=state.updated_at or datetime.now(timezone.utc),
        )
