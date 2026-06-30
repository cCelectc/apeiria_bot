from __future__ import annotations

from contextlib import suppress
from typing import Protocol

from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger

from .models import PendingRequest, ProcResult, RequestInfo


class RequestProvider(Protocol):
    key: str

    def supports(self, bot: Bot, event: Event) -> bool: ...

    def extract(self, bot: Bot, event: Event) -> RequestInfo | None: ...

    async def approve(
        self, bot: Bot, pending: PendingRequest, remark: str = ""
    ) -> ProcResult: ...

    async def reject(
        self, bot: Bot, pending: PendingRequest, reason: str = ""
    ) -> ProcResult: ...


def _safe_str(obj: object, attr: str) -> str:
    with suppress(Exception):
        v = getattr(obj, attr, None)
        if v is not None:
            return str(v)
    return ""


class OneBotV11FriendshipProvider:
    key = "onebot_v11"

    def supports(self, bot: Bot, event: Event) -> bool:
        if bot.adapter.get_name() != "OneBot V11":
            return False
        with suppress(Exception):
            return event.get_type() == "request"
        return False

    def extract(self, _bot: Bot, event: Event) -> RequestInfo | None:
        request_type = _safe_str(event, "request_type")
        sub_type = _safe_str(event, "sub_type")

        if request_type == "friend":
            kind = "friend"
        elif request_type == "group" and sub_type == "add":
            kind = "group_add"
        elif request_type == "group" and sub_type == "invite":
            kind = "group_invite"
        else:
            return None

        requester_id = _safe_str(event, "user_id")
        if not requester_id:
            return None

        flag = _safe_str(event, "flag")
        if not flag:
            return None

        return RequestInfo(
            kind=kind,
            requester_id=requester_id,
            requester_name=requester_id,
            platform="OneBot V11",
            raw_flag=flag,
            group_id=_safe_str(event, "group_id") or None,
            comment=_safe_str(event, "comment"),
            sub_type=sub_type if kind != "friend" else None,
        )

    async def approve(
        self, bot: Bot, pending: PendingRequest, remark: str = ""
    ) -> ProcResult:
        try:
            if pending.kind == "friend":
                await bot.set_friend_add_request(
                    flag=pending.raw_flag, approve=True, remark=remark
                )
            else:
                await bot.set_group_add_request(
                    flag=pending.raw_flag,
                    sub_type=pending.sub_type or "add",
                    approve=True,
                )
            return ProcResult(success=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("approve request failed: {}", exc)
            return ProcResult(success=False, message=str(exc))

    async def reject(
        self, bot: Bot, pending: PendingRequest, reason: str = ""
    ) -> ProcResult:
        try:
            if pending.kind == "friend":
                await bot.set_friend_add_request(flag=pending.raw_flag, approve=False)
            else:
                await bot.set_group_add_request(
                    flag=pending.raw_flag,
                    sub_type=pending.sub_type or "add",
                    approve=False,
                    reason=reason,
                )
            return ProcResult(success=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("reject request failed: {}", exc)
            return ProcResult(success=False, message=str(exc))


_SATORI_APPROVE_API = "handle_friend_request"
_SATORI_GUILD_API = "handle_guild_request"


class SatoriFriendshipProvider:
    key = "satori"

    def supports(self, bot: Bot, event: Event) -> bool:
        if bot.adapter.get_name() != "Satori":
            return False
        with suppress(Exception):
            return event.get_type() == "request"
        return False

    def extract(self, _bot: Bot, event: Event) -> RequestInfo | None:
        request_type = _safe_str(event, "request_type")
        if request_type == "friend":
            kind = "friend"
        elif request_type in ("guild", "guild-member"):
            kind = "group_add"
        else:
            return None
        requester_id = _safe_str(event, "user_id")
        if not requester_id:
            return None
        flag = _safe_str(event, "flag")
        if not flag:
            return None
        gid = _safe_str(event, "guild_id") or _safe_str(event, "group_id") or None
        return RequestInfo(
            kind=kind,
            requester_id=requester_id,
            requester_name=requester_id,
            platform="Satori",
            raw_flag=flag,
            group_id=gid,
            comment=_safe_str(event, "comment"),
        )

    async def approve(
        self, bot: Bot, pending: PendingRequest, remark: str = ""
    ) -> ProcResult:
        api = _SATORI_APPROVE_API if pending.kind == "friend" else _SATORI_GUILD_API
        try:
            await bot.call_api(
                api,
                message_id=pending.raw_flag,
                approve=True,
                comment=remark,
            )
            return ProcResult(success=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("satori approve failed: {}", exc)
            return ProcResult(success=False, message=str(exc))

    async def reject(
        self, bot: Bot, pending: PendingRequest, reason: str = ""
    ) -> ProcResult:
        api = _SATORI_APPROVE_API if pending.kind == "friend" else _SATORI_GUILD_API
        try:
            await bot.call_api(
                api,
                message_id=pending.raw_flag,
                approve=False,
                comment=reason,
            )
            return ProcResult(success=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("satori reject failed: {}", exc)
            return ProcResult(success=False, message=str(exc))


class MilkyFriendshipProvider:
    key = "milky"

    def supports(self, bot: Bot, event: Event) -> bool:
        if bot.adapter.get_name() != "Milky":
            return False
        with suppress(Exception):
            return event.get_type() == "request"
        return False

    def extract(self, _bot: Bot, event: Event) -> RequestInfo | None:
        request_type = _safe_str(event, "request_type")
        sub_type = _safe_str(event, "sub_type")
        if request_type == "friend":
            kind = "friend"
        elif request_type == "group" and sub_type == "add":
            kind = "group_add"
        elif request_type == "group" and sub_type == "invite":
            kind = "group_invite"
        else:
            return None
        requester_id = _safe_str(event, "user_id")
        if not requester_id:
            return None
        flag = _safe_str(event, "flag")
        if not flag:
            return None
        return RequestInfo(
            kind=kind,
            requester_id=requester_id,
            requester_name=requester_id,
            platform="Milky",
            raw_flag=flag,
            group_id=_safe_str(event, "group_id") or None,
            comment=_safe_str(event, "comment"),
            sub_type=sub_type if kind != "friend" else None,
        )

    async def approve(
        self, bot: Bot, pending: PendingRequest, remark: str = ""
    ) -> ProcResult:
        try:
            if pending.kind == "friend":
                await bot.call_api(
                    "set_friend_add_request",
                    flag=pending.raw_flag,
                    approve=True,
                    remark=remark,
                )
            else:
                await bot.call_api(
                    "set_group_add_request",
                    flag=pending.raw_flag,
                    sub_type=pending.sub_type or "add",
                    approve=True,
                )
            return ProcResult(success=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("milky approve failed: {}", exc)
            return ProcResult(success=False, message=str(exc))

    async def reject(
        self, bot: Bot, pending: PendingRequest, reason: str = ""
    ) -> ProcResult:
        try:
            if pending.kind == "friend":
                await bot.call_api(
                    "set_friend_add_request",
                    flag=pending.raw_flag,
                    approve=False,
                )
            else:
                await bot.call_api(
                    "set_group_add_request",
                    flag=pending.raw_flag,
                    sub_type=pending.sub_type or "add",
                    approve=False,
                    reason=reason,
                )
            return ProcResult(success=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("milky reject failed: {}", exc)
            return ProcResult(success=False, message=str(exc))


_providers: list[RequestProvider] = [
    OneBotV11FriendshipProvider(),
    SatoriFriendshipProvider(),
    MilkyFriendshipProvider(),
]


def resolve_provider(bot: Bot, event: Event) -> RequestProvider | None:
    for p in _providers:
        with suppress(Exception):
            if p.supports(bot, event):
                return p
    return None


def get_provider_by_key(key: str) -> RequestProvider | None:
    for p in _providers:
        if p.key == key:
            return p
    return None
