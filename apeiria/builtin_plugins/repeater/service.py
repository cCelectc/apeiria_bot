from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import log1p
from random import random
from typing import TYPE_CHECKING, Literal

from nonebot.log import logger

if TYPE_CHECKING:
    from .config import RepeaterConfig

ContentSegment = tuple[str, str]
ContentKey = tuple[ContentSegment, ...]
IGNORED_COMMAND_PREFIX = "/"
SkipReason = Literal[
    "inactive_config",
    "not_group_message",
    "platform_disabled",
    "group_disallowed",
    "bot_message",
    "unsupported_message",
    "ignored_prefix",
    "same_user_duplicate",
    "below_threshold",
    "probability_not_met",
    "round_already_triggered",
]

SUPPORTED_TEXT_TYPES = frozenset({"text", "plain"})
SUPPORTED_EMOJI_TYPES = frozenset({"emoji", "face", "mface", "market_face", "sticker"})
SUPPORTED_IMAGE_TYPES = frozenset({"image", "picture", "photo"})
UNSUPPORTED_SEGMENT_TYPES = frozenset(
    {
        "reply",
        "forward",
        "node",
        "json",
        "xml",
        "card",
        "markdown",
    }
)
EMOJI_ID_KEYS = ("id", "emoji_id", "face_id", "file_id")
IMAGE_ID_KEYS = ("file_id", "file", "id", "image_id", "uuid", "md5")


@dataclass(frozen=True, slots=True)
class RepeaterEvent:
    platform: str | None
    group_id: str | None
    user_id: str | None
    bot_id: str | None
    message: object

    @property
    def group_scope(self) -> str | None:
        if self.platform is None or self.group_id is None:
            return None
        return f"{self.platform}:{self.group_id}"

    @property
    def is_bot_message(self) -> bool:
        return (
            self.user_id is not None
            and self.bot_id is not None
            and self.user_id == self.bot_id
        )


@dataclass(frozen=True, slots=True)
class RepeatRoundState:
    content_key: ContentKey
    message: object
    count: int
    last_user_id: str
    triggered: bool = False


@dataclass(frozen=True, slots=True)
class RepeatDecision:
    should_send: bool = False
    message: object | None = None
    probability: float | None = None
    reason: SkipReason | None = None
    group_scope: str | None = None


class RepeaterStateStore:
    """In-memory repeater state."""

    def __init__(self) -> None:
        self._states: dict[str, RepeatRoundState] = {}

    def get(self, group_scope: str) -> RepeatRoundState | None:
        return self._states.get(group_scope)

    def set(self, group_scope: str, state: RepeatRoundState) -> None:
        self._states[group_scope] = state

    def reset(self, group_scope: str) -> None:
        self._states.pop(group_scope, None)

    def clear(self) -> None:
        self._states.clear()


class RepeaterService:
    """Evaluate group repeat rounds without depending on matcher internals."""

    def __init__(
        self,
        *,
        state_store: RepeaterStateStore | None = None,
        random_draw: Callable[[], float] = random,
    ) -> None:
        self._state_store = state_store or RepeaterStateStore()
        self._random_draw = random_draw

    @property
    def state_store(self) -> RepeaterStateStore:
        return self._state_store

    def evaluate(
        self,
        event: RepeaterEvent,
        *,
        config: "RepeaterConfig",
    ) -> RepeatDecision:
        skip = self._precheck(event, config=config)
        if skip is not None:
            return skip
        if event.group_scope is None or event.user_id is None:
            return RepeatDecision(reason="unsupported_message")

        content_result = build_content_key(
            event.message,
        )
        content_key = self._resolved_content_key(content_result)
        if content_key is None:
            return self._unsupported_content_decision(
                event,
                content_result,
                config=config,
            )

        state, same_user_duplicate = self._next_state(
            group_scope=event.group_scope,
            content_key=content_key,
            message=event.message,
            user_id=event.user_id,
            config=config,
        )
        if same_user_duplicate:
            return RepeatDecision(
                reason="same_user_duplicate",
                group_scope=event.group_scope,
            )
        return self._decision_for_state(event, state, config=config)

    def _precheck(
        self,
        event: RepeaterEvent,
        *,
        config: "RepeaterConfig",
    ) -> RepeatDecision | None:
        group_scope = event.group_scope
        if not config.active:
            self._debug(config, "Group repeater inactive: {}", config.errors)
            return RepeatDecision(reason="inactive_config", group_scope=group_scope)
        scope_skip = self._scope_skip(event, config=config)
        if scope_skip is not None:
            return scope_skip
        if event.is_bot_message:
            self._debug(config, "Group repeater ignored bot message in {}", group_scope)
            return RepeatDecision(reason="bot_message", group_scope=group_scope)
        if event.user_id is None and group_scope is not None:
            self._state_store.reset(group_scope)
            self._debug(config, "Group repeater reset {}: missing user id", group_scope)
            return RepeatDecision(reason="unsupported_message", group_scope=group_scope)
        return None

    def _scope_skip(
        self,
        event: RepeaterEvent,
        *,
        config: "RepeaterConfig",
    ) -> RepeatDecision | None:
        group_scope = event.group_scope
        if event.platform is None or event.group_id is None or group_scope is None:
            self._debug(config, "Group repeater skipped non-group message")
            return RepeatDecision(reason="not_group_message")
        if event.platform not in config.platforms:
            self._debug(
                config,
                "Group repeater skipped disabled platform {}",
                event.platform,
            )
            return RepeatDecision(reason="platform_disabled", group_scope=group_scope)
        if not config.is_group_allowed(group_scope):
            self._debug(
                config,
                "Group repeater skipped disallowed group {}",
                group_scope,
            )
            return RepeatDecision(reason="group_disallowed", group_scope=group_scope)
        return None

    def _resolved_content_key(
        self,
        content_result: "ContentKeyResult",
    ) -> ContentKey | None:
        if content_result.status == "supported":
            return content_result.key
        return None

    def _unsupported_content_decision(
        self,
        event: RepeaterEvent,
        content_result: "ContentKeyResult",
        *,
        config: "RepeaterConfig",
    ) -> RepeatDecision:
        group_scope = event.group_scope or ""
        self._state_store.reset(group_scope)
        self._debug(
            config,
            "Group repeater reset {}: {}",
            group_scope,
            content_result.status,
        )
        return RepeatDecision(
            reason=content_result.reason,
            group_scope=group_scope,
        )

    def _decision_for_state(
        self,
        event: RepeaterEvent,
        state: RepeatRoundState,
        *,
        config: "RepeaterConfig",
    ) -> RepeatDecision:
        group_scope = event.group_scope or ""
        if state.triggered:
            return RepeatDecision(
                reason="round_already_triggered",
                group_scope=group_scope,
            )
        if state.count < config.repeat_threshold:
            self._debug(
                config,
                "Group repeater count below threshold in {}: {}/{}",
                group_scope,
                state.count,
                config.repeat_threshold,
            )
            return RepeatDecision(reason="below_threshold", group_scope=group_scope)

        probability = _probability_for_state(state, config)
        if self._random_draw() >= probability:
            self._debug(
                config,
                "Group repeater draw missed in {}: p={}",
                group_scope,
                probability,
            )
            return RepeatDecision(
                probability=probability,
                reason="probability_not_met",
                group_scope=group_scope,
            )

        locked = RepeatRoundState(
            content_key=state.content_key,
            message=state.message,
            count=state.count,
            last_user_id=state.last_user_id,
            triggered=True,
        )
        self._state_store.set(group_scope, locked)
        return RepeatDecision(
            should_send=True,
            message=state.message,
            probability=probability,
            group_scope=group_scope,
        )

    def mark_triggered(self, group_scope: str) -> None:
        state = self._state_store.get(group_scope)
        if state is None:
            return
        if state.triggered:
            return
        self._state_store.set(
            group_scope,
            RepeatRoundState(
                content_key=state.content_key,
                message=state.message,
                count=state.count,
                last_user_id=state.last_user_id,
                triggered=True,
            ),
        )

    def _next_state(
        self,
        *,
        group_scope: str,
        content_key: ContentKey,
        message: object,
        user_id: str,
        config: "RepeaterConfig",
    ) -> tuple[RepeatRoundState, bool]:
        previous = self._state_store.get(group_scope)
        if previous is None or previous.content_key != content_key:
            state = RepeatRoundState(
                content_key=content_key,
                message=message,
                count=1,
                last_user_id=user_id,
            )
            self._state_store.set(group_scope, state)
            return state, False

        if previous.last_user_id == user_id:
            self._debug(
                config,
                "Group repeater preserved same-user duplicate in {}",
                group_scope,
            )
            return previous, True

        state = RepeatRoundState(
            content_key=content_key,
            message=message,
            count=previous.count + 1,
            last_user_id=user_id,
            triggered=previous.triggered,
        )
        self._state_store.set(group_scope, state)
        return state, False

    def _debug(
        self,
        config: "RepeaterConfig",
        message: str,
        *args: object,
    ) -> None:
        if config.debug:
            logger.debug(message, *args)


@dataclass(frozen=True, slots=True)
class ContentKeyResult:
    status: Literal["supported", "unsupported"]
    key: ContentKey | None = None
    reason: SkipReason = "unsupported_message"


def build_content_key(
    message: object,
) -> ContentKeyResult:
    segments = tuple(iter_message_segments(message))
    segments = segments or _text_segments_from_message(message)
    if not segments:
        return ContentKeyResult(status="unsupported")

    if message_starts_with_ignored_prefix(segments):
        return ContentKeyResult(status="unsupported", reason="ignored_prefix")

    key_parts = tuple(
        _content_segment(segment_type, data) for segment_type, data in segments
    )
    if any(part is None for part in key_parts):
        return ContentKeyResult(status="unsupported")

    if not key_parts:
        return ContentKeyResult(status="unsupported")
    return ContentKeyResult(
        status="supported",
        key=tuple(part for part in key_parts if part is not None),
    )


def iter_message_segments(
    message: object,
) -> Iterable[tuple[str, Mapping[str, object]]]:
    if isinstance(message, str):
        return ()

    if isinstance(message, Mapping):
        segment = _segment_from_object(message)
        return (segment,) if segment is not None else ()

    if isinstance(message, Iterable):
        return tuple(
            segment
            for item in message
            if (segment := _segment_from_object(item)) is not None
        )

    segment = _segment_from_object(message)
    return (segment,) if segment is not None else ()


def message_starts_with_ignored_prefix(
    segments: Sequence[tuple[str, Mapping[str, object]]],
) -> bool:
    if not segments:
        return False
    first_type, first_data = segments[0]
    if first_type.strip().lower() not in SUPPORTED_TEXT_TYPES:
        return False
    text = str(first_data.get("text", ""))
    return text.startswith(IGNORED_COMMAND_PREFIX)


def repeat_probability(
    count: int,
    *,
    repeat_threshold: int,
    base_probability: float,
    max_probability: float,
    saturation_extra: int,
) -> float:
    if count < repeat_threshold:
        return 0.0
    extra = count - repeat_threshold
    if extra <= 0:
        return base_probability
    progress = min(1.0, log1p(extra) / log1p(saturation_extra))
    return base_probability + (max_probability - base_probability) * progress


def _segment_from_object(
    value: object,
) -> tuple[str, Mapping[str, object]] | None:
    if isinstance(value, Mapping):
        raw_type = value.get("type")
        raw_data = value.get("data", {})
    else:
        raw_type = getattr(value, "type", None)
        raw_data = getattr(value, "data", {})

    if not isinstance(raw_type, str):
        return None
    data = dict(raw_data) if isinstance(raw_data, Mapping) else {}
    return raw_type, data


def _string_message_text(message: object) -> str | None:
    if isinstance(message, str):
        return message
    return None


def _text_segments_from_message(
    message: object,
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    text = _string_message_text(message)
    if text is None:
        return ()
    return (("text", {"text": text}),)


def _content_segment(
    segment_type: str,
    data: Mapping[str, object],
) -> ContentSegment | None:
    normalized_type = segment_type.strip().lower()
    if normalized_type in UNSUPPORTED_SEGMENT_TYPES:
        return None
    if normalized_type in SUPPORTED_TEXT_TYPES:
        return "text", str(data.get("text", ""))
    if normalized_type in SUPPORTED_EMOJI_TYPES:
        return _stable_segment("emoji", data, EMOJI_ID_KEYS)
    if normalized_type in SUPPORTED_IMAGE_TYPES:
        return _stable_segment("image", data, IMAGE_ID_KEYS)
    return None


def _stable_segment(
    kind: str,
    data: Mapping[str, object],
    keys: tuple[str, ...],
) -> ContentSegment | None:
    stable_id = _first_stable_value(data, keys)
    if stable_id is None:
        return None
    return kind, stable_id


def _probability_for_state(
    state: RepeatRoundState,
    config: "RepeaterConfig",
) -> float:
    return repeat_probability(
        state.count,
        repeat_threshold=config.repeat_threshold,
        base_probability=config.base_probability,
        max_probability=config.max_probability,
        saturation_extra=config.saturation_extra,
    )


def _first_stable_value(
    data: Mapping[str, object],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


default_repeater_service = RepeaterService()


__all__ = [
    "IGNORED_COMMAND_PREFIX",
    "ContentKey",
    "ContentKeyResult",
    "RepeatDecision",
    "RepeatRoundState",
    "RepeaterEvent",
    "RepeaterService",
    "RepeaterStateStore",
    "build_content_key",
    "default_repeater_service",
    "iter_message_segments",
    "message_starts_with_ignored_prefix",
    "repeat_probability",
]
