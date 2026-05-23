from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketKind = Literal["friend_request", "bot_group_invite", "group_join_request"]
TicketStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "ignored",
    "expired",
    "suppressed",
    "failed",
]
ApprovalAction = Literal["approve", "reject", "ignore", "detail", "list"]
NotificationSceneType = Literal["private", "group"]


class NotificationRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_type: NotificationSceneType
    scene_id: str
    message_id: str

    @property
    def key(self) -> str:
        return notification_key(
            scene_type=self.scene_type,
            scene_id=self.scene_id,
            message_id=self.message_id,
        )


class ApprovalTicket(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    kind: TicketKind
    adapter: str
    bot_id: str
    user_id: str
    flag: str
    status: TicketStatus = "pending"
    group_id: str | None = None
    comment: str | None = None
    sub_type: str | None = None
    nickname: str = ""
    group_name: str = ""
    failure_reason: str | None = None
    created_at: str
    updated_at: str
    expires_at: str | None = None
    handled_at: str | None = None
    handled_by: str | None = None
    handled_reason: str | None = None
    notifications: list[NotificationRef] = Field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        return self.status != "pending"

    def with_notification(self, notification: NotificationRef) -> "ApprovalTicket":
        notifications = [
            item for item in self.notifications if item.key != notification.key
        ]
        notifications.append(notification)
        return replace_model(self, notifications=notifications)


class IncomingApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: TicketKind
    adapter: str
    bot_id: str
    user_id: str
    flag: str
    group_id: str | None = None
    comment: str | None = None
    sub_type: str | None = None
    nickname: str = ""
    group_name: str = ""

    @property
    def dedupe_key(self) -> str:
        return "|".join(
            [
                self.adapter,
                self.bot_id,
                self.kind,
                self.flag,
                self.group_id or "",
                self.user_id,
            ]
        )


class ApprovalCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: ApprovalAction
    ticket_id: str | None = None
    reason: str = ""
    missing_target: bool = False


class ApprovalActor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    scene_type: NotificationSceneType
    scene_id: str
    is_owner: bool = False
    is_superuser: bool = False


def utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def notification_key(
    *,
    scene_type: NotificationSceneType,
    scene_id: str,
    message_id: str,
) -> str:
    return f"{scene_type}:{scene_id}:{message_id}"


def replace_model(ticket: ApprovalTicket, **changes: object) -> ApprovalTicket:
    data = ticket.model_dump()
    data.update(changes)
    return ApprovalTicket.model_validate(data)


__all__ = [
    "ApprovalAction",
    "ApprovalActor",
    "ApprovalCommand",
    "ApprovalTicket",
    "IncomingApprovalRequest",
    "NotificationRef",
    "NotificationSceneType",
    "TicketKind",
    "TicketStatus",
    "notification_key",
    "parse_datetime",
    "replace_model",
    "utcnow_text",
]
