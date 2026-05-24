from __future__ import annotations

import json
import secrets
from typing import TYPE_CHECKING, Any

from apeiria.utils.files import atomic_write_text

from .models import (
    ApprovalTicket,
    IncomingApprovalRequest,
    NotificationRef,
    NotificationSceneType,
    TicketStatus,
    notification_key,
    parse_datetime,
    replace_model,
    utcnow_text,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_ID_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class ApprovalTicketStore:
    """Plugin-owned JSON persistence for contact approval tickets."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._path = path
        self._id_factory = id_factory or self._generate_ticket_id

    @property
    def path(self) -> Path:
        if self._path is not None:
            return self._path
        from nonebot_plugin_localstore import get_data_file

        return get_data_file("contact_approval", "tickets.json")

    def upsert_pending(
        self,
        request: IncomingApprovalRequest,
        *,
        expires_at: str | None,
    ) -> ApprovalTicket:
        data = self._read_data()
        tickets = self._tickets_from_data(data)
        now = utcnow_text()
        existing_index = self._find_pending_equivalent(tickets, request)
        if existing_index is not None:
            existing = tickets[existing_index]
            ticket = replace_model(
                existing,
                user_id=request.user_id,
                group_id=request.group_id,
                comment=request.comment,
                sub_type=request.sub_type,
                nickname=request.nickname,
                group_name=request.group_name,
                flag=request.flag,
                updated_at=now,
                expires_at=expires_at,
                failure_reason=None,
            )
            tickets[existing_index] = ticket
        else:
            ticket = ApprovalTicket(
                ticket_id=self._next_unique_id(tickets),
                kind=request.kind,
                adapter=request.adapter,
                bot_id=request.bot_id,
                user_id=request.user_id,
                group_id=request.group_id,
                comment=request.comment,
                sub_type=request.sub_type,
                nickname=request.nickname,
                group_name=request.group_name,
                flag=request.flag,
                status="pending",
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
            )
            tickets.append(ticket)
        self._write_tickets(tickets)
        return ticket

    def add_notification(
        self,
        ticket_id: str,
        notification: NotificationRef,
    ) -> ApprovalTicket | None:
        return self._replace_ticket(
            ticket_id,
            lambda ticket: ticket.with_notification(notification),
        )

    def get(self, ticket_id: str) -> ApprovalTicket | None:
        normalized = ticket_id.strip().upper()
        return next(
            (ticket for ticket in self.list_all() if ticket.ticket_id == normalized),
            None,
        )

    def get_by_notification(
        self,
        *,
        scene_type: NotificationSceneType,
        scene_id: str,
        message_id: str,
    ) -> ApprovalTicket | None:
        key = notification_key(
            scene_type=scene_type,
            scene_id=scene_id,
            message_id=message_id,
        )
        for ticket in self.list_all():
            if any(notification.key == key for notification in ticket.notifications):
                return ticket
        return None

    def list_all(self) -> list[ApprovalTicket]:
        return self._tickets_from_data(self._read_data())

    def list_pending(
        self,
        *,
        scene_type: NotificationSceneType | None = None,
        scene_id: str | None = None,
        kinds: set[str] | None = None,
    ) -> list[ApprovalTicket]:
        tickets = [ticket for ticket in self.list_all() if ticket.status == "pending"]
        if kinds is not None:
            tickets = [ticket for ticket in tickets if ticket.kind in kinds]
        if scene_type is not None and scene_id is not None:
            tickets = [
                ticket
                for ticket in tickets
                if self._ticket_matches_scene(
                    ticket,
                    scene_type=scene_type,
                    scene_id=scene_id,
                )
            ]
        return sorted(tickets, key=lambda ticket: ticket.created_at)

    def mark_terminal(
        self,
        ticket_id: str,
        *,
        status: TicketStatus,
        handled_by: str | None = None,
        handled_reason: str | None = None,
        failure_reason: str | None = None,
    ) -> tuple[ApprovalTicket | None, bool]:
        normalized = ticket_id.strip().upper()
        data = self._read_data()
        tickets = self._tickets_from_data(data)
        now = utcnow_text()
        for index, ticket in enumerate(tickets):
            if ticket.ticket_id != normalized:
                continue
            if ticket.status != "pending":
                return ticket, False
            updated = replace_model(
                ticket,
                status=status,
                updated_at=now,
                handled_at=now,
                handled_by=handled_by,
                handled_reason=handled_reason,
                failure_reason=failure_reason,
            )
            tickets[index] = updated
            self._write_tickets(tickets)
            return updated, True
        return None, False

    def mark_expired_if_needed(
        self,
        ticket: ApprovalTicket,
    ) -> tuple[ApprovalTicket, bool]:
        if ticket.status != "pending":
            return ticket, False
        expires_at = parse_datetime(ticket.expires_at)
        now = parse_datetime(utcnow_text())
        if expires_at is None or now is None or expires_at > now:
            return ticket, False
        updated, changed = self.mark_terminal(ticket.ticket_id, status="expired")
        return updated or ticket, changed

    def _replace_ticket(
        self,
        ticket_id: str,
        update: Callable[[ApprovalTicket], ApprovalTicket],
    ) -> ApprovalTicket | None:
        normalized = ticket_id.strip().upper()
        data = self._read_data()
        tickets = self._tickets_from_data(data)
        for index, ticket in enumerate(tickets):
            if ticket.ticket_id != normalized:
                continue
            updated = update(ticket)
            tickets[index] = replace_model(updated, updated_at=utcnow_text())
            self._write_tickets(tickets)
            return tickets[index]
        return None

    def _read_data(self) -> dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return {"tickets": []}
        return data if isinstance(data, dict) else {"tickets": []}

    def _tickets_from_data(self, data: dict[str, Any]) -> list[ApprovalTicket]:
        raw_tickets = data.get("tickets")
        if not isinstance(raw_tickets, list):
            return []
        tickets: list[ApprovalTicket] = []
        for item in raw_tickets:
            if not isinstance(item, dict):
                continue
            try:
                tickets.append(ApprovalTicket.model_validate(item))
            except ValueError:
                continue
        return tickets

    def _write_tickets(self, tickets: list[ApprovalTicket]) -> None:
        payload = {
            "version": 1,
            "tickets": [ticket.model_dump(mode="json") for ticket in tickets],
        }
        atomic_write_text(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        )

    def _find_pending_equivalent(
        self,
        tickets: list[ApprovalTicket],
        request: IncomingApprovalRequest,
    ) -> int | None:
        for index, ticket in enumerate(tickets):
            if ticket.status != "pending":
                continue
            if _ticket_dedupe_key(ticket) == request.dedupe_key:
                return index
        return None

    def _next_unique_id(self, tickets: list[ApprovalTicket]) -> str:
        existing = {ticket.ticket_id for ticket in tickets}
        while True:
            ticket_id = self._id_factory().upper()
            if ticket_id not in existing:
                return ticket_id

    def _generate_ticket_id(self) -> str:
        return "".join(secrets.choice(_ID_ALPHABET) for _ in range(4))

    def _ticket_matches_scene(
        self,
        ticket: ApprovalTicket,
        *,
        scene_type: NotificationSceneType,
        scene_id: str,
    ) -> bool:
        if scene_type == "group":
            return ticket.kind == "group_join_request" and ticket.group_id == scene_id
        return ticket.kind in {"friend_request", "bot_group_invite"}


def _ticket_dedupe_key(ticket: ApprovalTicket) -> str:
    return "|".join(
        [
            ticket.adapter,
            ticket.bot_id,
            ticket.kind,
            ticket.flag,
            ticket.group_id or "",
            ticket.user_id,
        ]
    )


approval_ticket_store = ApprovalTicketStore()


__all__ = ["ApprovalTicketStore", "approval_ticket_store"]
