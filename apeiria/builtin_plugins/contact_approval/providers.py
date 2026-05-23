from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar, cast

from nonebot.log import logger

from apeiria.bot.platform import adapter_name, id_value

from .models import ApprovalTicket, IncomingApprovalRequest

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nonebot.adapters import Bot, Event

    from .config import OwnerTarget

_ONEBOT_V11_ADAPTER_NAME = "onebotv11"


@dataclass(frozen=True, slots=True)
class ContactApprovalActionResult:
    status: str
    reason: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    @classmethod
    def succeeded(cls) -> "ContactApprovalActionResult":
        return cls(status="success")

    @classmethod
    def failed(
        cls,
        reason: str = "platform_operation_failed",
    ) -> "ContactApprovalActionResult":
        return cls(status="failed", reason=reason)

    @classmethod
    def unsupported(
        cls,
        reason: str = "unsupported",
    ) -> "ContactApprovalActionResult":
        return cls(status="unsupported", reason=reason)


@dataclass(frozen=True, slots=True)
class ContactApprovalNotificationResult(ContactApprovalActionResult):
    message_id: str | None = None

    @classmethod
    def delivered(
        cls,
        message_id: str | None = None,
    ) -> "ContactApprovalNotificationResult":
        return cls(status="success", message_id=message_id)

    @classmethod
    def failed(
        cls,
        reason: str = "platform_delivery_failed",
    ) -> "ContactApprovalNotificationResult":
        return cls(status="failed", reason=reason)

    @classmethod
    def unsupported(
        cls,
        reason: str = "unsupported",
    ) -> "ContactApprovalNotificationResult":
        return cls(status="unsupported", reason=reason)


class ContactApprovalProvider(Protocol):
    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    async def normalize_request(
        self,
        bot: "Bot",
        event: "Event",
    ) -> IncomingApprovalRequest | None: ...

    async def send_owner_notification(
        self,
        bot: "Bot",
        target: OwnerTarget,
        *,
        message: str,
    ) -> ContactApprovalNotificationResult: ...

    async def send_group_notification(
        self,
        bot: "Bot",
        *,
        group_id: str,
        message: str,
    ) -> ContactApprovalNotificationResult: ...

    async def is_group_operator(
        self,
        bot: "Bot",
        *,
        group_id: str,
        user_id: str,
    ) -> ContactApprovalActionResult: ...

    async def approve_ticket(
        self,
        bot: "Bot",
        ticket: ApprovalTicket,
    ) -> ContactApprovalActionResult: ...

    async def reject_ticket(
        self,
        bot: "Bot",
        ticket: ApprovalTicket,
        *,
        reason: str = "",
    ) -> ContactApprovalActionResult: ...


ProviderT = TypeVar("ProviderT", bound=ContactApprovalProvider)


class ContactApprovalProviderRegistry:
    def __init__(self, providers: tuple[ContactApprovalProvider, ...]) -> None:
        self._providers = providers

    def resolve(self, bot: "Bot", event: "Event") -> ContactApprovalProvider | None:
        for provider in self._providers:
            if self._provider_supports(provider, bot, event):
                return provider
        return None

    def _provider_supports(
        self,
        provider: ContactApprovalProvider,
        bot: "Bot",
        event: "Event",
    ) -> bool:
        try:
            return provider.supports(bot, event)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Contact-approval provider {} support check failed: {}",
                type(provider).__name__,
                exc,
            )
            return False


class OneBotV11ContactApprovalProvider:
    """OneBot v11 provider for relationship approval requests."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        del event
        return adapter_name(bot) == _ONEBOT_V11_ADAPTER_NAME

    async def normalize_request(
        self,
        bot: "Bot",
        event: "Event",
    ) -> IncomingApprovalRequest | None:
        request_type = _string_attr(event, "request_type")
        user_id = _string_attr(event, "user_id")
        flag = _string_attr(event, "flag")
        if request_type is None or user_id is None or flag is None:
            return None

        if request_type == "friend":
            return IncomingApprovalRequest(
                kind="friend_request",
                adapter=adapter_name(bot),
                bot_id=str(getattr(bot, "self_id", "")),
                user_id=user_id,
                flag=flag,
                comment=_string_attr(event, "comment"),
                nickname=await self._resolve_user_label(bot, user_id),
            )

        if request_type != "group":
            return None

        group_id = _string_attr(event, "group_id")
        sub_type = _string_attr(event, "sub_type")
        if group_id is None or sub_type not in {"add", "invite"}:
            return None
        return IncomingApprovalRequest(
            kind="bot_group_invite" if sub_type == "invite" else "group_join_request",
            adapter=adapter_name(bot),
            bot_id=str(getattr(bot, "self_id", "")),
            user_id=user_id,
            group_id=group_id,
            flag=flag,
            comment=_string_attr(event, "comment"),
            sub_type=sub_type,
            nickname=await self._resolve_user_label(bot, user_id),
            group_name=await self._resolve_group_label(bot, group_id),
        )

    async def send_owner_notification(
        self,
        bot: "Bot",
        target: OwnerTarget,
        *,
        message: str,
    ) -> ContactApprovalNotificationResult:
        if target.scope != "qq":
            return ContactApprovalNotificationResult.unsupported(
                "unsupported_owner_scope"
            )
        result = await _call_api_for_result(
            bot,
            "send_private_msg",
            user_id=id_value(target.target_id),
            message=message,
        )
        if isinstance(result, _APIFailure):
            return ContactApprovalNotificationResult.failed(result.reason)
        return ContactApprovalNotificationResult.delivered(
            _message_id_from_result(result)
        )

    async def send_group_notification(
        self,
        bot: "Bot",
        *,
        group_id: str,
        message: str,
    ) -> ContactApprovalNotificationResult:
        result = await _call_api_for_result(
            bot,
            "send_group_msg",
            group_id=id_value(group_id),
            message=message,
        )
        if isinstance(result, _APIFailure):
            return ContactApprovalNotificationResult.failed(result.reason)
        return ContactApprovalNotificationResult.delivered(
            _message_id_from_result(result)
        )

    async def is_group_operator(
        self,
        bot: "Bot",
        *,
        group_id: str,
        user_id: str,
    ) -> ContactApprovalActionResult:
        result = await _call_api_for_result(
            bot,
            "get_group_member_info",
            group_id=id_value(group_id),
            user_id=id_value(user_id),
            no_cache=True,
        )
        if isinstance(result, _APIFailure):
            return ContactApprovalActionResult.failed("operator_role_unavailable")
        if not isinstance(result, dict):
            return ContactApprovalActionResult.failed("operator_role_invalid")
        role = str(result.get("role") or "").strip().lower()
        if role in {"owner", "admin"}:
            return ContactApprovalActionResult.succeeded()
        return ContactApprovalActionResult.failed("operator_not_group_manager")

    async def approve_ticket(
        self,
        bot: "Bot",
        ticket: ApprovalTicket,
    ) -> ContactApprovalActionResult:
        if ticket.kind == "friend_request":
            return await _call_onebot_action(
                bot,
                "set_friend_add_request",
                flag=ticket.flag,
                approve=True,
                remark="",
            )
        if ticket.kind in {"bot_group_invite", "group_join_request"}:
            return await _call_onebot_action(
                bot,
                "set_group_add_request",
                flag=ticket.flag,
                sub_type=ticket.sub_type or "",
                approve=True,
            )
        return ContactApprovalActionResult.unsupported("unsupported_ticket_kind")

    async def reject_ticket(
        self,
        bot: "Bot",
        ticket: ApprovalTicket,
        *,
        reason: str = "",
    ) -> ContactApprovalActionResult:
        if ticket.kind == "friend_request":
            return await _call_onebot_action(
                bot,
                "set_friend_add_request",
                flag=ticket.flag,
                approve=False,
            )
        if ticket.kind in {"bot_group_invite", "group_join_request"}:
            return await _call_onebot_action(
                bot,
                "set_group_add_request",
                flag=ticket.flag,
                sub_type=ticket.sub_type or "",
                approve=False,
                reason=reason,
            )
        return ContactApprovalActionResult.unsupported("unsupported_ticket_kind")

    async def _resolve_user_label(self, bot: "Bot", user_id: str) -> str:
        result = await _call_api_for_result(
            bot,
            "get_stranger_info",
            user_id=id_value(user_id),
        )
        if isinstance(result, _APIFailure) or not isinstance(result, dict):
            return ""
        return str(result.get("nickname") or "").strip()

    async def _resolve_group_label(self, bot: "Bot", group_id: str) -> str:
        result = await _call_api_for_result(
            bot,
            "get_group_info",
            group_id=id_value(group_id),
        )
        if isinstance(result, _APIFailure) or not isinstance(result, dict):
            return ""
        return str(result.get("group_name") or "").strip()


@dataclass(frozen=True, slots=True)
class _APIFailure:
    reason: str


async def _call_onebot_action(
    bot: object,
    api: str,
    **data: object,
) -> ContactApprovalActionResult:
    result = await _call_api_for_result(bot, api, **data)
    if isinstance(result, _APIFailure):
        return ContactApprovalActionResult.failed(result.reason)
    return ContactApprovalActionResult.succeeded()


async def _call_api_for_result(bot: object, api: str, **data: object) -> object:
    call_api = getattr(bot, "call_api", None)
    if not callable(call_api):
        return _APIFailure("platform_api_unavailable")
    try:
        return await cast("Callable[..., Awaitable[object]]", call_api)(api, **data)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Contact-approval API {} failed: {}", api, exc)
        return _APIFailure("platform_operation_failed")


def _message_id_from_result(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    value = result.get("message_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_attr(value: object, name: str) -> str | None:
    try:
        item = getattr(value, name, None)
    except Exception:  # noqa: BLE001
        return None
    if item is None:
        return None
    text = str(item).strip()
    return text or None


contact_approval_provider_registry = ContactApprovalProviderRegistry(
    providers=(OneBotV11ContactApprovalProvider(),)
)


__all__ = [
    "ContactApprovalActionResult",
    "ContactApprovalNotificationResult",
    "ContactApprovalProvider",
    "ContactApprovalProviderRegistry",
    "OneBotV11ContactApprovalProvider",
    "contact_approval_provider_registry",
]
