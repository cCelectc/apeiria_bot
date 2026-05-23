from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from nonebot.log import logger

from apeiria.bot.platform import (
    ActionResult,
    adapter_name,
    call_platform_api,
    id_value,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_QQ_SCOPE = "qq"


@dataclass(frozen=True, slots=True)
class OwnerTarget:
    scope: str
    target_id: str


@dataclass(frozen=True, slots=True)
class ContactOwnerDeliveryResult(ActionResult):
    """Result for bounded owner-message delivery."""


class ContactOwnerProvider(Protocol):
    """Adapter capability boundary consumed by the contact-owner plugin."""

    def supports(
        self,
        bot: "Bot",
        event: "Event",
        target: OwnerTarget,
    ) -> bool: ...

    async def deliver_owner_message(
        self,
        bot: "Bot",
        event: "Event",
        target: OwnerTarget,
        *,
        message: str,
    ) -> ContactOwnerDeliveryResult: ...


class ContactOwnerProviderRegistry:
    """Resolve the first provider that supports a bot/event/target tuple."""

    def __init__(self, providers: tuple[ContactOwnerProvider, ...]) -> None:
        self._providers = providers

    def resolve(
        self,
        bot: "Bot",
        event: "Event",
        target: OwnerTarget,
    ) -> ContactOwnerProvider | None:
        for provider in self._providers:
            if self._provider_supports(provider, bot, event, target):
                return provider
        return None

    def _provider_supports(
        self,
        provider: ContactOwnerProvider,
        bot: "Bot",
        event: "Event",
        target: OwnerTarget,
    ) -> bool:
        try:
            return provider.supports(bot, event, target)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Contact-owner provider {} support check failed: {}",
                type(provider).__name__,
                exc,
            )
            return False


class OneBotV11ContactOwnerProvider:
    """OneBot v11 provider for QQ private-message owner delivery."""

    def supports(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: OwnerTarget,
    ) -> bool:
        return (
            adapter_name(bot) == _ONEBOT_V11_ADAPTER_NAME and target.scope == _QQ_SCOPE
        )

    async def deliver_owner_message(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: OwnerTarget,
        *,
        message: str,
    ) -> ContactOwnerDeliveryResult:
        return await call_platform_api(
            bot,
            "send_private_msg",
            data={
                "user_id": id_value(target.target_id),
                "message": message,
            },
            result_type=ContactOwnerDeliveryResult,
            log_label="Contact owner OneBot",
        )


def parse_owner_target(value: str) -> OwnerTarget | None:
    text = value.strip()
    if ":" not in text:
        return None
    raw_scope, raw_target_id = text.split(":", maxsplit=1)
    scope = raw_scope.strip().lower()
    target_id = raw_target_id.strip()
    if not scope or not target_id:
        return None
    if scope == _QQ_SCOPE and not _valid_qq_user_id(target_id):
        return None
    return OwnerTarget(scope=scope, target_id=target_id)


def _valid_qq_user_id(value: str) -> bool:
    return value.isdecimal() and value != "0"


contact_owner_provider_registry = ContactOwnerProviderRegistry(
    providers=(OneBotV11ContactOwnerProvider(),)
)


__all__ = [
    "ContactOwnerDeliveryResult",
    "ContactOwnerProvider",
    "ContactOwnerProviderRegistry",
    "OneBotV11ContactOwnerProvider",
    "OwnerTarget",
    "contact_owner_provider_registry",
    "parse_owner_target",
]
