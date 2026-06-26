from __future__ import annotations

from random import random
from typing import TYPE_CHECKING

from nonebot.log import logger

from .evaluation import (
    IGNORED_COMMAND_PREFIX,
    ContentKeyResult,
    build_content_key,
    iter_message_segments,
    message_starts_with_ignored_prefix,
    repeat_probability,
)
from .state import (
    ContentKey,
    RepeatDecision,
    RepeaterEvent,
    RepeaterStateStore,
    RepeatRoundState,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from .config import RepeaterConfig


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
        content_result: ContentKeyResult,
    ) -> ContentKey | None:
        if content_result.status == "supported":
            return content_result.key
        return None

    def _unsupported_content_decision(
        self,
        event: RepeaterEvent,
        content_result: ContentKeyResult,
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
