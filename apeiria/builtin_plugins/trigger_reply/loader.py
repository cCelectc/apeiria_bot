from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import import_module
from math import isfinite
from typing import TYPE_CHECKING, Any, cast

from nonebot.log import logger

from .models import (
    FilterMode,
    MatchType,
    TriggerCooldown,
    TriggerEntry,
    TriggerFilter,
    TriggerMatch,
    TriggerReply,
    TriggerRuleSet,
    TriggerScene,
    TriggerSceneFilter,
    compile_regex,
)

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

_MATCH_TYPES: frozenset[str] = frozenset(
    {"full", "fuzzy", "start", "end", "regex", "poke"}
)
_POKE_EVENTS: frozenset[str] = frozenset({"poke", "qq.poke"})
_FILTER_TYPES: frozenset[str] = frozenset({"black", "white"})
_COOLDOWN_SCOPES: frozenset[str] = frozenset({"entry", "user", "group"})
_SCENES: frozenset[str] = frozenset({"group", "private"})


def _toml_module() -> ModuleType:
    try:
        return import_module("tomllib")
    except ModuleNotFoundError:
        return import_module("tomli")


class TriggerRuleSetCache:
    def __init__(self) -> None:
        self._ruleset = TriggerRuleSet(status="missing")
        self.load_count = 0

    @property
    def ruleset(self) -> TriggerRuleSet:
        return self._ruleset

    def load(self, path: Path) -> TriggerRuleSet:
        self._ruleset = load_trigger_rule_set(path)
        self.load_count += 1
        return self._ruleset

    def set(self, ruleset: TriggerRuleSet) -> None:
        self._ruleset = ruleset

    def clear(self) -> None:
        self._ruleset = TriggerRuleSet(status="missing")
        self.load_count = 0


def load_trigger_rule_set(path: Path) -> TriggerRuleSet:
    if not path.exists():
        return TriggerRuleSet(status="missing", source_path=str(path))
    try:
        with path.open("rb") as file:
            payload = _toml_module().load(file)
    except Exception as exc:  # noqa: BLE001
        return TriggerRuleSet(
            status="invalid",
            errors=(f"failed to read rules file: {exc}",),
            source_path=str(path),
        )
    try:
        entries, errors = _load_entries(payload)
    except (TypeError, ValueError) as exc:
        return TriggerRuleSet(
            status="invalid",
            errors=(str(exc),),
            source_path=str(path),
        )
    return TriggerRuleSet(
        entries=tuple(sorted(entries, key=lambda entry: entry.priority)),
        status="active",
        errors=tuple(errors),
        source_path=str(path),
    )


def load_trigger_rule_sets(paths: Sequence[Path]) -> TriggerRuleSet:
    rule_sets = tuple(load_trigger_rule_set(path) for path in paths)
    invalid = tuple(ruleset for ruleset in rule_sets if ruleset.status == "invalid")
    if invalid:
        return TriggerRuleSet(
            status="invalid",
            errors=tuple(
                error for ruleset in invalid for error in _source_errors(ruleset)
            ),
            source_path=_joined_source_path(paths),
        )
    entries: list[TriggerEntry] = []
    errors: list[str] = []
    seen_entry_ids: set[str] = set()
    active_sources = tuple(
        ruleset for ruleset in rule_sets if ruleset.status == "active"
    )
    for ruleset in rule_sets:
        if ruleset.status == "missing" and active_sources:
            errors.append(f"{ruleset.source_path}: rules file missing")
        errors.extend(_source_errors(ruleset))
        for entry in ruleset.entries:
            if entry.id in seen_entry_ids:
                errors.append(
                    f"{ruleset.source_path}: duplicate entry id ignored: {entry.id}"
                )
                continue
            seen_entry_ids.add(entry.id)
            entries.append(entry)
    return TriggerRuleSet(
        entries=tuple(sorted(entries, key=lambda entry: entry.priority)),
        status="active" if active_sources else "missing",
        errors=tuple(errors),
        source_path=_joined_source_path(paths),
    )


def _source_errors(ruleset: TriggerRuleSet) -> tuple[str, ...]:
    source = ruleset.source_path or "<unknown>"
    return tuple(f"{source}: {error}" for error in ruleset.errors)


def _joined_source_path(paths: Sequence[Path]) -> str:
    return ", ".join(str(path) for path in paths)


def _load_entries(payload: object) -> tuple[list[TriggerEntry], list[str]]:
    if not isinstance(payload, Mapping):
        msg = "rules file must be a TOML table"
        raise TypeError(msg)
    entries: list[TriggerEntry] = []
    errors: list[str] = []
    for index, (entry_id, raw_entry) in enumerate(payload.items()):
        try:
            entry, entry_errors = _load_entry(
                raw_entry,
                entry_id=str(entry_id),
                index=index,
            )
        except (TypeError, ValueError) as exc:  # noqa: PERF203
            errors.append(f"{entry_id}: {exc}")
        else:
            entries.append(entry)
            errors.extend(f"{entry_id}: {error}" for error in entry_errors)
    return entries, errors


def _load_entry(
    raw: object,
    *,
    entry_id: str,
    index: int,
) -> tuple[TriggerEntry, list[str]]:
    if not isinstance(raw, Mapping):
        msg = "entry must be a table"
        raise TypeError(msg)
    normalized_entry_id = _string_value(entry_id)
    if normalized_entry_id is None:
        normalized_entry_id = f"entry-{index + 1}"
    matches, match_errors = _load_matches(raw)
    matches = tuple(matches)
    replies, reply_errors = _load_replies(raw.get("reply"))
    replies = tuple(replies)
    if not matches:
        detail = "; ".join(match_errors)
        msg = "entry must contain at least one valid match"
        raise ValueError(f"{msg}: {detail}" if detail else msg)
    if not replies:
        detail = "; ".join(reply_errors)
        msg = "entry must contain at least one reply"
        raise ValueError(f"{msg}: {detail}" if detail else msg)
    scenes, scene_errors = _load_scenes(raw.get("scenes"))
    groups, group_errors = _load_filter(raw.get("groups"), label="groups")
    users, user_errors = _load_filter(raw.get("users"), label="users")
    entry = TriggerEntry(
        id=normalized_entry_id,
        enabled=_bool_value(raw.get("enabled"), fallback=True),
        priority=_int_value(raw.get("priority"), fallback=1, minimum=1),
        block=_bool_value(raw.get("block"), fallback=True),
        chance=_float_value(
            raw.get("chance"),
            fallback=1.0,
            minimum=0.0,
            maximum=1.0,
        ),
        scenes=scenes,
        groups=groups,
        users=users,
        cooldown=_load_cooldown(raw.get("cooldown")),
        matches=matches,
        replies=replies,
    )
    return entry, [
        *match_errors,
        *reply_errors,
        *scene_errors,
        *group_errors,
        *user_errors,
    ]


def _load_matches(raw: Mapping[object, object]) -> tuple[list[TriggerMatch], list[str]]:
    matches: list[TriggerMatch] = []
    errors: list[str] = []
    raw_match = raw.get("match")
    for index, item in enumerate(_list_value(raw_match, strip=False)):
        try:
            matches.append(_load_match(_shorthand_match(raw, item)))
        except (TypeError, ValueError) as exc:  # noqa: PERF203
            errors.append(f"match[{index}]: {exc}")
            logger.debug("Trigger-reply ignored invalid match {}: {}", index, exc)
    raw_event = _string_value(raw.get("event"))
    if raw_event is not None:
        try:
            matches.append(_load_event_match(raw, raw_event))
        except (TypeError, ValueError) as exc:
            errors.append(f"event: {exc}")
            logger.debug("Trigger-reply ignored invalid event match: {}", exc)
    raw_matches = raw.get("matches")
    if raw_matches is not None:
        if not isinstance(raw_matches, Sequence) or isinstance(raw_matches, str):
            msg = "matches must be a list"
            raise TypeError(msg)
        for index, item in enumerate(raw_matches):
            try:
                matches.append(_load_match(item))
            except (TypeError, ValueError) as exc:  # noqa: PERF203
                errors.append(f"matches[{index}]: {exc}")
                logger.debug("Trigger-reply ignored invalid match {}: {}", index, exc)
    return matches, errors


def _shorthand_match(raw: Mapping[object, object], pattern: str) -> dict[str, object]:
    return {
        "type": raw.get("type"),
        "match": pattern,
        "to_me": raw.get("to_me"),
        "ignore_case": raw.get("ignore_case"),
        "strip": raw.get("strip"),
        "allow_plaintext": raw.get("allow_plaintext"),
    }


def _load_event_match(raw: Mapping[object, object], event: str) -> TriggerMatch:
    normalized = event.lower()
    if normalized not in _POKE_EVENTS:
        msg = f"unsupported event: {event}"
        raise ValueError(msg)
    return _load_match(
        {
            "type": "poke",
            "to_me": raw.get("to_me"),
        }
    )


def _load_match(raw: object) -> TriggerMatch:
    if isinstance(raw, str):
        raw = {"match": raw}
    if not isinstance(raw, Mapping):
        msg = "match must be a string or table"
        raise TypeError(msg)
    match_type = _match_type(raw.get("type"))
    pattern = _string_value(raw.get("match"), strip=False)
    if match_type != "poke" and pattern is None:
        msg = "message match requires match text"
        raise ValueError(msg)
    ignore_case = _bool_value(raw.get("ignore_case"), fallback=True)
    compiled = None
    if match_type == "regex" and pattern is not None:
        try:
            compiled = compile_regex(pattern, ignore_case=ignore_case)
        except Exception as exc:
            msg = f"invalid regex: {exc}"
            raise ValueError(msg) from exc
    return TriggerMatch(
        type=match_type,
        pattern=pattern,
        to_me=_bool_value(raw.get("to_me"), fallback=match_type == "poke"),
        ignore_case=ignore_case,
        strip=_bool_value(raw.get("strip"), fallback=True),
        allow_plaintext=_bool_value(raw.get("allow_plaintext"), fallback=True),
        compiled_pattern=compiled,
    )


def _load_replies(raw: object) -> tuple[list[TriggerReply], list[str]]:
    if raw is None:
        return [], []
    if isinstance(raw, str):
        text = _string_value(raw, strip=False)
        return ([TriggerReply(text=text)] if text else []), []
    if not isinstance(raw, Sequence):
        msg = "reply must be a string, string list, or weighted reply list"
        raise TypeError(msg)
    if not raw:
        return [], []
    if all(isinstance(item, str) for item in raw):
        return [
            TriggerReply(text=text)
            for item in raw
            if (text := _string_value(item, strip=False)) is not None
        ], []
    if all(isinstance(item, Mapping) for item in raw):
        replies: list[TriggerReply] = []
        errors: list[str] = []
        for index, item in enumerate(raw):
            text = _string_value(  # type: ignore[union-attr]
                item.get("text"),
                strip=False,
            )
            weight = _float_value(
                item.get("weight"),  # type: ignore[union-attr]
                fallback=1.0,
                minimum=0.0,
            )
            if text is None:
                errors.append(f"reply[{index}]: weighted reply requires text")
                continue
            if weight <= 0:
                errors.append(f"reply[{index}]: weighted reply requires weight > 0")
                continue
            replies.append(TriggerReply(text=text, weight=weight))
        return replies, errors
    msg = "reply list cannot mix strings and weighted reply tables"
    raise TypeError(msg)


def _load_filter(raw: object, *, label: str) -> tuple[TriggerFilter, list[str]]:
    if raw is None:
        return TriggerFilter(), []
    if isinstance(raw, Mapping):
        mode, mode_errors = _filter_mode(raw.get("mode", raw.get("type")), label=label)
        candidates = _list_value(raw.get("values"))
        values = [item for item in candidates if _is_scoped_value(item)]
        errors = _invalid_filter_errors(label, candidates, values)
        return (
            TriggerFilter(
                mode=mode,
                values=frozenset(values),
                valid=not mode_errors and (not candidates or bool(values)),
            ),
            [*mode_errors, *errors],
        )
    candidates = _list_value(raw)
    values = [item for item in candidates if _is_scoped_value(item)]
    errors = _invalid_filter_errors(label, candidates, values)
    return (
        TriggerFilter(
            mode="white",
            values=frozenset(values),
            valid=not candidates or bool(values),
        ),
        errors,
    )


def _load_scenes(raw: object) -> tuple[TriggerSceneFilter, list[str]]:
    if raw is None:
        return TriggerSceneFilter(), []
    scenes = tuple(_list_value(raw))
    valid_scenes = tuple(scene for scene in scenes if scene in _SCENES)
    invalid_scenes = tuple(scene for scene in scenes if scene not in _SCENES)
    return (
        TriggerSceneFilter(
            values=frozenset(cast("TriggerScene", scene) for scene in valid_scenes),
            valid=not scenes or bool(valid_scenes),
        ),
        [f"scenes contains unsupported value: {scene}" for scene in invalid_scenes],
    )


def _load_cooldown(raw: object) -> TriggerCooldown | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float, str)) and not isinstance(raw, bool):
        seconds = _float_value(raw, fallback=0.0, minimum=0.0)
        return TriggerCooldown(seconds=seconds) if seconds > 0 else None
    if not isinstance(raw, Mapping):
        return None
    seconds = _float_value(
        raw.get("seconds", raw.get("time")),
        fallback=0.0,
        minimum=0.0,
    )
    if seconds <= 0:
        return None
    scope = _string_value(raw.get("scope")) or "group"
    if scope not in _COOLDOWN_SCOPES:
        scope = "group"
    return TriggerCooldown(seconds=seconds, scope=cast("Any", scope))


def _match_type(value: object) -> MatchType:
    text = (_string_value(value) or "full").lower()
    if text == "exact":
        text = "full"
    if text == "contains":
        text = "fuzzy"
    if text == "startswith":
        text = "start"
    if text == "endswith":
        text = "end"
    if text not in _MATCH_TYPES:
        msg = f"unsupported match type: {text}"
        raise ValueError(msg)
    return text  # type: ignore[return-value]


def _filter_mode(value: object, *, label: str) -> tuple[FilterMode, list[str]]:
    text = (_string_value(value) or "white").lower()
    if text in {"allow", "white", "whitelist"}:
        return "white", []
    if text in _FILTER_TYPES:
        return text, []  # type: ignore[return-value]
    return "white", [f"{label} contains unsupported filter mode: {text}"]


def _is_scoped_value(value: str) -> bool:
    platform, separator, target = value.partition(":")
    return bool(platform and separator and target)


def _invalid_filter_errors(
    label: str,
    candidates: list[str],
    values: list[str],
) -> list[str]:
    valid_values = set(values)
    return [
        f"{label} contains unsupported scoped value: {item}"
        for item in candidates
        if item not in valid_values
    ]


def _list_value(value: object, *, strip: bool = True) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _string_value(value, strip=strip)
        return [text] if text is not None else []
    if isinstance(value, Sequence):
        values: list[str] = []
        for item in value:
            text = _string_value(item, strip=strip)
            if text:
                values.append(text)
        return values
    text = _string_value(value, strip=strip)
    return [text] if text else []


def _string_value(value: object, *, strip: bool = True) -> str | None:
    if value is None:
        return None
    text = str(value)
    if strip:
        text = text.strip()
        return text or None
    return text if text.strip() else None


def _bool_value(value: object, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return fallback


def _int_value(value: object, *, fallback: int, minimum: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return max(result, minimum)


def _float_value(
    value: object,
    *,
    fallback: float,
    minimum: float,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool):
        return fallback
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if not isfinite(result):
        return fallback
    result = max(result, minimum)
    if maximum is not None:
        result = min(result, maximum)
    return result


default_rule_set_cache = TriggerRuleSetCache()


__all__ = [
    "TriggerRuleSetCache",
    "default_rule_set_cache",
    "load_trigger_rule_set",
    "load_trigger_rule_sets",
]
