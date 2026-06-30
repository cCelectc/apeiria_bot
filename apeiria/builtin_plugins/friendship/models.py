from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

RequestKind = Literal["friend", "group_add", "group_invite"]


@dataclass
class RequestInfo:
    kind: RequestKind
    requester_id: str
    requester_name: str
    platform: str
    raw_flag: str
    group_id: str | None = None
    group_name: str | None = None
    comment: str = ""
    sub_type: str | None = None


@dataclass
class PendingRequest:
    id: str
    provider_key: str
    bot_self_id: str
    scope: str
    raw_flag: str
    kind: RequestKind
    requester_id: str
    requester_name: str
    comment: str = ""
    sub_type: str | None = None
    group_id: str | None = None
    group_name: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    notified: dict[str, str] = field(default_factory=dict)


@dataclass
class ProcResult:
    success: bool
    message: str = ""
