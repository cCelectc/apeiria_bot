from __future__ import annotations

import re
from dataclasses import dataclass, field
from re import Pattern
from typing import Literal

TriggerSource = Literal["message", "poke"]
MatchType = Literal["full", "fuzzy", "start", "end", "regex", "poke"]
FilterMode = Literal["black", "white"]
CooldownScope = Literal["entry", "user", "group"]
RuleSetStatus = Literal["active", "missing", "invalid"]
TriggerScene = Literal["group", "private"]


@dataclass(frozen=True, slots=True)
class TriggerFilter:
    mode: FilterMode = "white"
    values: frozenset[str] = frozenset()
    valid: bool = True

    def allows(self, value: str | None) -> bool:
        if not self.valid:
            return False
        if not self.values:
            return True
        matched = value is not None and _target_matches(value, self.values)
        return matched if self.mode == "white" else not matched


@dataclass(frozen=True, slots=True)
class TriggerSceneFilter:
    values: frozenset[TriggerScene] = frozenset()
    valid: bool = True

    def allows(self, value: TriggerScene) -> bool:
        if not self.valid:
            return False
        return not self.values or value in self.values


@dataclass(frozen=True, slots=True)
class TriggerCooldown:
    seconds: float
    scope: CooldownScope = "group"


@dataclass(frozen=True, slots=True)
class TriggerMatch:
    type: MatchType = "full"
    pattern: str | None = None
    to_me: bool = False
    ignore_case: bool = True
    strip: bool = True
    allow_plaintext: bool = True
    compiled_pattern: Pattern[str] | None = None

    @property
    def source(self) -> TriggerSource:
        return "poke" if self.type == "poke" else "message"


@dataclass(frozen=True, slots=True)
class TriggerReply:
    text: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class TriggerEntry:
    id: str
    enabled: bool = True
    priority: int = 1
    block: bool = True
    chance: float = 1.0
    scenes: TriggerSceneFilter = field(default_factory=TriggerSceneFilter)
    groups: TriggerFilter = field(default_factory=TriggerFilter)
    users: TriggerFilter = field(default_factory=TriggerFilter)
    cooldown: TriggerCooldown | None = None
    matches: tuple[TriggerMatch, ...] = ()
    replies: tuple[TriggerReply, ...] = ()


@dataclass(frozen=True, slots=True)
class TriggerRuleSet:
    entries: tuple[TriggerEntry, ...] = ()
    status: RuleSetStatus = "active"
    errors: tuple[str, ...] = ()
    source_path: str | None = None

    @property
    def active(self) -> bool:
        return self.status in {"active", "missing"}


@dataclass(frozen=True, slots=True)
class TriggerInput:
    source: TriggerSource
    platform: str | None = None
    bot_id: str | None = None
    user_id: str | None = None
    group_id: str | None = None
    message_id: str | None = None
    message_text: str = ""
    plaintext: str = ""
    target_id: str | None = None
    is_to_me: bool = False

    @property
    def scene(self) -> TriggerScene:
        return "group" if self.group_id is not None else "private"

    @property
    def scoped_group_id(self) -> str | None:
        return _scoped_id(self.platform, self.group_id)

    @property
    def scoped_user_id(self) -> str | None:
        return _scoped_id(self.platform, self.user_id)


@dataclass(frozen=True, slots=True)
class MatchResult:
    match: TriggerMatch
    trigger: str = ""
    rest: str = ""
    variables: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TriggerReplyDecision:
    entry: TriggerEntry
    reply: str
    match: TriggerMatch
    cooldown_key: str | None = None
    cooldown_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class TriggerEvaluationResult:
    decisions: tuple[TriggerReplyDecision, ...] = ()

    @property
    def should_reply(self) -> bool:
        return bool(self.decisions)


def compile_regex(pattern: str, *, ignore_case: bool) -> Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(pattern, flags)


def _scoped_id(platform: str | None, value: str | None) -> str | None:
    if platform is None or value is None:
        return None
    return f"{platform}:{value}"


def _target_matches(value: str, candidates: frozenset[str]) -> bool:
    if value in candidates:
        return True
    platform, separator, _target = value.partition(":")
    return bool(separator and f"{platform}:*" in candidates)


__all__ = [
    "CooldownScope",
    "FilterMode",
    "MatchResult",
    "MatchType",
    "TriggerCooldown",
    "TriggerEntry",
    "TriggerEvaluationResult",
    "TriggerFilter",
    "TriggerInput",
    "TriggerMatch",
    "TriggerReply",
    "TriggerReplyDecision",
    "TriggerRuleSet",
    "TriggerScene",
    "TriggerSceneFilter",
    "TriggerSource",
    "compile_regex",
]
