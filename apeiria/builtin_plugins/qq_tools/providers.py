"""Adapter-aware QQ action providers for AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

from nonebot.log import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nonebot.adapters import Bot, Event

from apeiria.bot.platform import (
    ActionResult,
    ActionStatus,
    ProviderRegistry,
    adapter_name,
    call_platform_api,
    event_group_id,
    event_message_id,
    event_user_id,
    id_value,
)

QQReaction = Literal["like"]
QQActionStatus = ActionStatus

_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_ONEBOT_LIKE_EMOJI_ID = "124"
_MAX_GROUP_MEMBER_RESULTS = 20


@dataclass(frozen=True, slots=True)
class QQActionResult(ActionResult):
    """Provider-neutral result for one bounded QQ action."""


@dataclass(frozen=True, slots=True)
class QQPokeRequest:
    """Provider-neutral request to poke the current actor."""

    user_id: str
    group_id: str | None = None


@dataclass(frozen=True, slots=True)
class QQMessageReactionRequest:
    """Provider-neutral request to react to the current/source message."""

    message_id: str
    reaction: QQReaction


@dataclass(frozen=True, slots=True)
class QQGroupMember:
    """Provider-neutral current-group member record for AI lookup."""

    user_id: str
    nickname: str = ""
    group_card: str = ""
    role: str = "member"

    def matches(self, keyword: str) -> bool:
        if not keyword:
            return True
        haystack = f"{self.user_id}{self.nickname}{self.group_card}{self.role}"
        return keyword in haystack

    def to_payload(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "group_card": self.group_card,
            "role": self.role,
        }


@dataclass(frozen=True, slots=True)
class QQGroupMemberLookupResult(QQActionResult):
    """Result for bounded current-group member lookup."""

    group_id: str | None = None
    members: tuple[QQGroupMember, ...] = ()
    total_matches: int = 0
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class QQMentionFragmentResult(QQActionResult):
    """Result containing a provider-normalized mention fragment."""

    user_id: str | None = None
    mention: str | None = None


class QQToolProvider(Protocol):
    """Adapter capability boundary consumed by QQ AI tools."""

    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    async def poke_current_actor(
        self,
        bot: "Bot",
        event: "Event",
    ) -> QQActionResult: ...

    async def react_to_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        reaction: QQReaction,
    ) -> QQActionResult: ...

    async def get_group_members(
        self,
        bot: "Bot",
        event: "Event",
        *,
        keyword: str = "",
        limit: int = _MAX_GROUP_MEMBER_RESULTS,
    ) -> QQGroupMemberLookupResult: ...

    async def mention_user(
        self,
        bot: "Bot",
        event: "Event",
        *,
        user_id: str,
    ) -> QQMentionFragmentResult: ...


class QQToolProviderRegistry(ProviderRegistry[QQToolProvider]):
    """Resolve the first provider that supports a bot/event pair."""

    def __init__(self, providers: tuple[QQToolProvider, ...]) -> None:
        super().__init__(providers, label="QQ tools provider")


class OneBotV11QQToolProvider:
    """OneBot v11 provider for bounded QQ current-scene actions."""

    def supports(self, bot: "Bot", event: "Event") -> bool:  # noqa: ARG002
        return adapter_name(bot) == _ONEBOT_V11_ADAPTER_NAME

    async def poke_current_actor(
        self,
        bot: "Bot",
        event: "Event",
    ) -> QQActionResult:
        request = _poke_request_from_event(event)
        if request is None:
            return QQActionResult.unsupported("poke_target_unavailable")

        payload: dict[str, object] = {"user_id": id_value(request.user_id)}
        if request.group_id is not None:
            payload["group_id"] = id_value(request.group_id)
            payload["target_id"] = id_value(request.user_id)

        return await _call_onebot_api(bot, "send_poke", **payload)

    async def react_to_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        reaction: QQReaction,
    ) -> QQActionResult:
        request = _reaction_request_from_event(event, reaction=reaction)
        if request is None:
            return QQActionResult.unsupported("message_target_unavailable")

        return await _call_onebot_api(
            bot,
            "set_msg_emoji_like",
            message_id=_message_id_value(request.message_id),
            emoji_id=_emoji_id_for_reaction(request.reaction),
        )

    async def get_group_members(
        self,
        bot: "Bot",
        event: "Event",
        *,
        keyword: str = "",
        limit: int = _MAX_GROUP_MEMBER_RESULTS,
    ) -> QQGroupMemberLookupResult:
        group_id = event_group_id(event)
        if group_id is None:
            return QQGroupMemberLookupResult.unsupported("group_context_unavailable")

        raw_members = await _call_onebot_api_for_result(
            bot,
            "get_group_member_list",
            group_id=id_value(group_id),
        )
        if raw_members is None:
            return QQGroupMemberLookupResult.unsupported("platform_api_unavailable")
        if isinstance(raw_members, _OneBotAPIFailure):
            return QQGroupMemberLookupResult.failed("platform_operation_failed")
        if not isinstance(raw_members, list):
            return QQGroupMemberLookupResult.failed("platform_response_invalid")

        members = tuple(
            member
            for raw_member in raw_members
            if (member := _member_from_onebot_payload(raw_member)) is not None
        )
        normalized_keyword = keyword.strip()
        matched = tuple(
            member for member in members if member.matches(normalized_keyword)
        )
        safe_limit = max(1, min(limit, _MAX_GROUP_MEMBER_RESULTS))
        returned = matched[:safe_limit]
        return QQGroupMemberLookupResult(
            status="success",
            group_id=group_id,
            members=returned,
            total_matches=len(matched),
            truncated=len(matched) > len(returned),
        )

    async def mention_user(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        user_id: str,
    ) -> QQMentionFragmentResult:
        normalized_user_id = user_id.strip()
        if not _valid_numeric_user_id(normalized_user_id):
            return QQMentionFragmentResult.unsupported("invalid_user_id")
        return QQMentionFragmentResult(
            status="success",
            user_id=normalized_user_id,
            mention=f"[CQ:at,qq={normalized_user_id}]",
        )


def _poke_request_from_event(event: object) -> QQPokeRequest | None:
    user_id = event_user_id(event)
    if user_id is None:
        return None
    return QQPokeRequest(
        user_id=user_id,
        group_id=event_group_id(event),
    )


def _reaction_request_from_event(
    event: object,
    *,
    reaction: QQReaction,
) -> QQMessageReactionRequest | None:
    message_id = event_message_id(event)
    if message_id is None:
        return None
    return QQMessageReactionRequest(message_id=message_id, reaction=reaction)


def _message_id_value(message_id: str) -> int | str:
    return id_value(message_id)


def _emoji_id_for_reaction(reaction: QQReaction) -> str:
    emoji_ids: dict[QQReaction, str] = {"like": _ONEBOT_LIKE_EMOJI_ID}
    return emoji_ids[reaction]


def _member_from_onebot_payload(raw: object) -> QQGroupMember | None:
    if not isinstance(raw, dict):
        return None
    user_id = _string_payload_value(raw.get("user_id"))
    if user_id is None:
        return None
    return QQGroupMember(
        user_id=user_id,
        nickname=_string_payload_value(raw.get("nickname")) or "",
        group_card=_string_payload_value(raw.get("card")) or "",
        role=_string_payload_value(raw.get("role")) or "member",
    )


def _string_payload_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _valid_numeric_user_id(user_id: str) -> bool:
    return user_id.isdecimal() and user_id != "0"


async def _call_onebot_api(
    bot: "Bot",
    api: str,
    **data: object,
) -> QQActionResult:
    return await call_platform_api(
        bot,
        api,
        data=data,
        result_type=QQActionResult,
        log_label="QQ tools OneBot",
    )


async def _call_onebot_api_for_result(
    bot: "Bot",
    api: str,
    **data: object,
) -> object | None:
    call_api = getattr(bot, "call_api", None)
    if not callable(call_api):
        return None
    try:
        return await cast("Callable[..., Awaitable[object]]", call_api)(api, **data)
    except Exception as exc:  # noqa: BLE001
        logger.debug("QQ tools OneBot API {} failed: {}", api, exc)
        return _OneBotAPIFailure()


class _OneBotAPIFailure:
    pass


qq_tool_provider_registry = QQToolProviderRegistry(
    providers=(OneBotV11QQToolProvider(),)
)


__all__ = [
    "OneBotV11QQToolProvider",
    "QQActionResult",
    "QQGroupMember",
    "QQGroupMemberLookupResult",
    "QQMentionFragmentResult",
    "QQMessageReactionRequest",
    "QQPokeRequest",
    "QQReaction",
    "QQToolProvider",
    "QQToolProviderRegistry",
    "qq_tool_provider_registry",
]
