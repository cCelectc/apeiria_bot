"""Small helpers for built-in plugins that perform live platform actions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, Literal, Protocol, TypeVar, cast

from nonebot.log import logger
from typing_extensions import Self

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

ActionStatus = Literal["success", "failed", "unsupported"]
ResultT = TypeVar("ResultT", bound="ActionResult")
ProviderT = TypeVar("ProviderT", bound="SupportsPlatformScene")


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Result for one bounded best-effort platform operation."""

    status: ActionStatus
    reason: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    @classmethod
    def succeeded(cls) -> Self:
        return cls(status="success")

    @classmethod
    def failed(
        cls,
        reason: str = "platform_operation_failed",
    ) -> Self:
        return cls(status="failed", reason=reason)

    @classmethod
    def unsupported(
        cls,
        reason: str = "unsupported",
    ) -> Self:
        return cls(status="unsupported", reason=reason)


class SupportsPlatformScene(Protocol):
    """Provider protocol for matching a live bot/event pair."""

    def supports(self, bot: "Bot", event: "Event") -> bool: ...


class ProviderRegistry(Generic[ProviderT]):
    """Resolve the first provider that supports a bot/event pair."""

    def __init__(
        self,
        providers: tuple[ProviderT, ...],
        *,
        label: str = "platform provider",
    ) -> None:
        self._providers = providers
        self._label = label

    def resolve(
        self,
        bot: "Bot",
        event: "Event",
    ) -> ProviderT | None:
        for provider in self._providers:
            if self._provider_supports(provider, bot, event):
                return provider
        return None

    def _provider_supports(
        self,
        provider: ProviderT,
        bot: "Bot",
        event: "Event",
    ) -> bool:
        try:
            return provider.supports(bot, event)
        except Exception as exc:  # noqa: BLE001
            logger.debug("{} support check failed: {}", self._label, exc)
            return False


def adapter_name(bot: object) -> str:
    """Return a compact lower-case adapter name for comparisons."""

    adapter_type = str(getattr(bot, "type", "") or "").lower()
    return adapter_type.replace(" ", "")


def string_attr(value: object, name: str) -> str | None:
    """Read one string-like attribute without propagating adapter errors."""

    try:
        item = getattr(value, name, None)
    except Exception:  # noqa: BLE001
        return None
    return _non_empty_string(item)


def nested_string_attr(value: object, *names: str) -> str | None:
    """Read a nested string-like attribute path safely."""

    current = value
    for name in names:
        try:
            current = getattr(current, name, None)
        except Exception:  # noqa: BLE001
            return None
        if current is None:
            return None
    return _non_empty_string(current)


def mapping_string_attr(value: object, key: str) -> str | None:
    """Read a string-like mapping value safely."""

    if not isinstance(value, Mapping):
        return None
    return _non_empty_string(value.get(key))


def event_user_id(event: object) -> str | None:
    """Return a current event user id from common adapter shapes."""

    value = _call_string_getter(event, "get_user_id")
    if value is not None:
        return value
    return string_attr(event, "user_id")


def event_group_id(event: object) -> str | None:
    """Return a current event group id from common adapter shapes."""

    return string_attr(event, "group_id")


def event_message_id(event: object) -> str | None:
    """Return a current event message id from common adapter shapes."""

    value = _call_string_getter(event, "get_message_id")
    if value is not None:
        return value
    return string_attr(event, "message_id")


def id_value(value: str) -> int | str:
    """Convert numeric id text to int while preserving non-numeric ids."""

    try:
        return int(value)
    except ValueError:
        return value


async def call_platform_api(  # noqa: PLR0913
    bot: object,
    api: str,
    *,
    data: Mapping[str, object] | None = None,
    result_type: type[ResultT] = ActionResult,
    failed_reason: str = "platform_operation_failed",
    unavailable_reason: str = "platform_api_unavailable",
    log_label: str = "Platform",
) -> ResultT:
    """Call ``bot.call_api`` and convert failures into bounded results."""

    payload = dict(data or {})
    call_api = getattr(bot, "call_api", None)
    if not callable(call_api):
        return result_type.unsupported(unavailable_reason)
    try:
        await cast("Callable[..., Awaitable[object]]", call_api)(api, **payload)
    except Exception as exc:  # noqa: BLE001
        logger.debug("{} API {} failed: {}", log_label, api, exc)
        return result_type.failed(failed_reason)
    return result_type.succeeded()


def _call_string_getter(value: object, name: str) -> str | None:
    getter = getattr(value, name, None)
    if not callable(getter):
        return None
    try:
        item = getter()
    except Exception:  # noqa: BLE001
        return None
    return _non_empty_string(item)


def _non_empty_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "ActionResult",
    "ActionStatus",
    "ProviderRegistry",
    "adapter_name",
    "call_platform_api",
    "event_group_id",
    "event_message_id",
    "event_user_id",
    "id_value",
    "mapping_string_attr",
    "nested_string_attr",
    "string_attr",
]
