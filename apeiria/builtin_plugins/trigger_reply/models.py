from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

MatchType = Literal["full", "fuzzy", "start", "end", "regex"]
TriggerScene = Literal["group", "private"]


@dataclass
class IdFilter:
    mode: Literal["white", "black"] = "white"
    values: frozenset[str] = field(default_factory=frozenset)

    def __bool__(self) -> bool:
        return len(self.values) > 0


class TriggerReply(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    weight: float = 1.0


class TriggerMatch:
    __slots__ = sorted(
        (
            "type",
            "pattern",
            "to_me",
            "ignore_case",
            "strip",
            "allow_plaintext",
            "compiled_pattern",
        )
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        _type: MatchType = "full",
        pattern: str | None = None,
        to_me: bool = False,
        ignore_case: bool = True,
        strip: bool = True,
        allow_plaintext: bool = True,
        compiled_pattern: re.Pattern[str] | None = None,
    ) -> None:
        self.type = _type
        self.pattern = pattern
        self.to_me = to_me
        self.ignore_case = ignore_case
        self.strip = strip
        self.allow_plaintext = allow_plaintext
        self.compiled_pattern = compiled_pattern


class TriggerEntry:
    __slots__ = sorted(
        (
            "id",
            "enabled",
            "priority",
            "block",
            "chance",
            "scenes",
            "groups",
            "users",
            "matches",
            "replies",
        )
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        _id: str,
        enabled: bool = True,
        priority: int = 1,
        block: bool = True,
        chance: float = 1.0,
        scenes: frozenset[TriggerScene] = frozenset(),
        groups: IdFilter | None = None,
        users: IdFilter | None = None,
        matches: tuple[TriggerMatch, ...] = (),
        replies: tuple[TriggerReply, ...] = (),
    ) -> None:
        self.id = _id
        self.enabled = enabled
        self.priority = priority
        self.block = block
        self.chance = chance
        self.scenes = scenes
        self.groups = groups or IdFilter()
        self.users = users or IdFilter()
        self.matches = matches
        self.replies = replies


class TriggerInput:
    __slots__ = sorted(
        (
            "platform",
            "bot_id",
            "user_id",
            "group_id",
            "message_text",
            "plaintext",
            "is_to_me",
        )
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        platform: str | None = None,
        bot_id: str | None = None,
        user_id: str | None = None,
        group_id: str | None = None,
        message_text: str = "",
        plaintext: str = "",
        is_to_me: bool = False,
    ) -> None:
        self.platform = platform
        self.bot_id = bot_id
        self.user_id = user_id
        self.group_id = group_id
        self.message_text = message_text
        self.plaintext = plaintext
        self.is_to_me = is_to_me

    @property
    def scene(self) -> TriggerScene:
        return "group" if self.group_id is not None else "private"
