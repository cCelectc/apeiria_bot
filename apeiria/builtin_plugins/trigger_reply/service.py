from __future__ import annotations

from random import choices, random
from time import monotonic
from typing import TYPE_CHECKING, overload

from .models import (
    MatchResult,
    TriggerEntry,
    TriggerEvaluationResult,
    TriggerInput,
    TriggerMatch,
    TriggerReplyDecision,
    TriggerRuleSet,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class TriggerReplyCooldownStore:
    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._expires_at: dict[str, float] = {}

    def is_active(self, key: str) -> bool:
        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return False
        if expires_at <= self._clock():
            self._expires_at.pop(key, None)
            return False
        return True

    def mark(self, key: str, seconds: float) -> None:
        if seconds <= 0:
            return
        self._expires_at[key] = self._clock() + seconds

    def release(self, key: str) -> None:
        self._expires_at.pop(key, None)

    def clear(self) -> None:
        self._expires_at.clear()


class TriggerReplyService:
    def __init__(
        self,
        *,
        cooldown_store: TriggerReplyCooldownStore | None = None,
        random_draw: Callable[[], float] = random,
        reply_choice: Callable[[tuple[str, ...]], str] | None = None,
    ) -> None:
        self._cooldown_store = cooldown_store or TriggerReplyCooldownStore()
        self._random_draw = random_draw
        self._reply_choice = reply_choice

    @property
    def cooldown_store(self) -> TriggerReplyCooldownStore:
        return self._cooldown_store

    def evaluate(
        self,
        trigger: TriggerInput,
        *,
        ruleset: TriggerRuleSet,
    ) -> TriggerEvaluationResult:
        if not ruleset.active:
            return TriggerEvaluationResult()
        decisions: list[TriggerReplyDecision] = []
        for entry in sorted(ruleset.entries, key=lambda item: item.priority):
            if not self._entry_can_match(entry, trigger):
                continue
            cooldown_key = self._cooldown_key(entry, trigger)
            if cooldown_key is not None and self._cooldown_store.is_active(
                cooldown_key
            ):
                continue
            match_result = self._match_entry(entry, trigger)
            if match_result is None:
                continue
            if entry.chance < 1.0 and self._random_draw() >= entry.chance:
                continue
            reply = self._select_reply(entry, trigger, match_result)
            decisions.append(
                TriggerReplyDecision(
                    entry=entry,
                    reply=reply,
                    match=match_result.match,
                    cooldown_key=cooldown_key,
                    cooldown_seconds=(
                        entry.cooldown.seconds if entry.cooldown is not None else 0.0
                    ),
                )
            )
            if entry.block:
                break
        return TriggerEvaluationResult(decisions=tuple(decisions))

    @overload
    def commit_cooldowns(self, result: TriggerEvaluationResult, /) -> None: ...

    @overload
    def commit_cooldowns(
        self,
        result: Iterable[TriggerReplyDecision],
        /,
    ) -> None: ...

    def commit_cooldowns(
        self,
        result: TriggerEvaluationResult | Iterable[TriggerReplyDecision],
        /,
    ) -> None:
        for decision in _iter_decisions(result):
            if decision.cooldown_key is None:
                continue
            self._cooldown_store.mark(
                decision.cooldown_key,
                decision.cooldown_seconds,
            )

    def reserve_cooldowns(
        self,
        result: TriggerEvaluationResult | Iterable[TriggerReplyDecision],
        /,
    ) -> None:
        self.commit_cooldowns(result)

    def release_cooldowns(
        self,
        result: TriggerEvaluationResult | Iterable[TriggerReplyDecision],
        /,
    ) -> None:
        for decision in _iter_decisions(result):
            if decision.cooldown_key is not None:
                self._cooldown_store.release(decision.cooldown_key)

    def _entry_can_match(self, entry: TriggerEntry, trigger: TriggerInput) -> bool:
        return (
            entry.enabled
            and bool(entry.matches)
            and bool(entry.replies)
            and entry.scenes.allows(trigger.scene)
            and entry.groups.allows(trigger.scoped_group_id)
            and entry.users.allows(trigger.scoped_user_id)
        )

    def _match_entry(
        self,
        entry: TriggerEntry,
        trigger: TriggerInput,
    ) -> MatchResult | None:
        for match in entry.matches:
            if match.source != trigger.source:
                continue
            result = self._match(trigger, match)
            if result is not None:
                return result
        return None

    def _match(self, trigger: TriggerInput, match: TriggerMatch) -> MatchResult | None:
        if match.to_me and not trigger.is_to_me:
            return None
        if match.type == "poke":
            return MatchResult(match=match, trigger="poke")
        if match.pattern is None:
            return None
        message_text = trigger.message_text
        plaintext = trigger.plaintext
        pattern = match.pattern
        if match.strip:
            message_text = message_text.strip()
            plaintext = plaintext.strip()
            pattern = pattern.strip()
        compare_message = message_text
        compare_plaintext = plaintext
        compare_pattern = pattern
        if match.ignore_case and match.type != "regex":
            compare_message = compare_message.lower()
            compare_plaintext = compare_plaintext.lower()
            compare_pattern = compare_pattern.lower()
        return self._match_message(
            match,
            message_text=message_text,
            plaintext=plaintext,
            pattern=pattern,
            compare_message=compare_message,
            compare_plaintext=compare_plaintext,
            compare_pattern=compare_pattern,
        )

    def _match_message(  # noqa: PLR0913
        self,
        match: TriggerMatch,
        *,
        message_text: str,
        plaintext: str,
        pattern: str,
        compare_message: str,
        compare_plaintext: str,
        compare_pattern: str,
    ) -> MatchResult | None:
        if match.type == "regex":
            return self._match_regex(
                match,
                message_text=message_text,
                plaintext=plaintext,
            )
        matched = False
        trigger_text = message_text
        if match.type == "full":
            matched = compare_message == compare_pattern
            if not matched and match.allow_plaintext:
                matched = compare_plaintext == compare_pattern
                trigger_text = plaintext
        elif match.type == "start":
            matched = compare_message.startswith(compare_pattern)
            if not matched and match.allow_plaintext:
                matched = compare_plaintext.startswith(compare_pattern)
                trigger_text = plaintext
        elif match.type == "end":
            matched = compare_message.endswith(compare_pattern)
            if not matched and match.allow_plaintext:
                matched = compare_plaintext.endswith(compare_pattern)
                trigger_text = plaintext
        else:
            matched = compare_pattern in compare_message
            if not matched and match.allow_plaintext:
                matched = compare_pattern in compare_plaintext
                trigger_text = plaintext
        if not matched:
            return None
        return MatchResult(
            match=match,
            trigger=match.pattern or trigger_text,
            rest=_rest_for_match(match, trigger_text=trigger_text, pattern=pattern),
        )

    def _match_regex(
        self,
        match: TriggerMatch,
        *,
        message_text: str,
        plaintext: str,
    ) -> MatchResult | None:
        if match.compiled_pattern is None:
            return None
        regex_match = match.compiled_pattern.search(message_text)
        if regex_match is None and match.allow_plaintext:
            regex_match = match.compiled_pattern.search(plaintext)
        if regex_match is None:
            return None
        groups = regex_match.groups()
        variables = {"v0": regex_match.group(0)}
        for index, value in enumerate(groups, start=1):
            variables[f"v{index}"] = value or ""
        for key, value in regex_match.groupdict().items():
            variables[key] = value or ""
        return MatchResult(
            match=match,
            trigger=regex_match.group(0),
            rest=groups[0].strip() if groups and groups[0] is not None else "",
            variables=variables,
        )

    def _select_reply(
        self,
        entry: TriggerEntry,
        trigger: TriggerInput,
        match_result: MatchResult,
    ) -> str:
        if self._reply_choice is not None:
            text = self._reply_choice(tuple(reply.text for reply in entry.replies))
        else:
            texts = tuple(reply.text for reply in entry.replies)
            weights = tuple(reply.weight for reply in entry.replies)
            text = choices(texts, weights=weights, k=1)[0]
        return _render_reply(text, trigger, match_result)

    def _cooldown_key(
        self,
        entry: TriggerEntry,
        trigger: TriggerInput,
    ) -> str | None:
        cooldown = entry.cooldown
        if cooldown is None:
            return None
        if cooldown.scope == "user":
            scope = trigger.scoped_user_id or trigger.user_id
        elif cooldown.scope == "group":
            scope = trigger.scoped_group_id or trigger.scoped_user_id or trigger.user_id
        else:
            scope = "global"
        if scope is None:
            return None
        return f"{entry.id}:{cooldown.scope}:{scope}"


def _render_reply(
    template: str,
    trigger: TriggerInput,
    match_result: MatchResult,
) -> str:
    values = {
        "self_id": trigger.bot_id or "",
        "bot_id": trigger.bot_id or "",
        "message_id": trigger.message_id or "",
        "user_id": trigger.user_id or "",
        "group_id": trigger.group_id or "",
        "target_id": trigger.target_id or "",
        "message": trigger.message_text,
        "text": trigger.plaintext,
        "plaintext": trigger.plaintext,
        "trigger": match_result.trigger,
        "rest": match_result.rest,
        **match_result.variables,
    }
    try:
        return template.format_map(_SafeFormatDict(values))
    except Exception:  # noqa: BLE001
        return template


class _SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _rest_for_match(match: TriggerMatch, *, trigger_text: str, pattern: str) -> str:
    if match.type != "start":
        return ""
    return trigger_text[len(pattern) :].strip()


def _iter_decisions(
    result: TriggerEvaluationResult | Iterable[TriggerReplyDecision],
) -> Iterable[TriggerReplyDecision]:
    return result.decisions if isinstance(result, TriggerEvaluationResult) else result


default_trigger_reply_service = TriggerReplyService()


__all__ = [
    "TriggerReplyCooldownStore",
    "TriggerReplyService",
    "default_trigger_reply_service",
]
