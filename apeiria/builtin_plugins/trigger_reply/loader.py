from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from math import isfinite
from pathlib import Path  # noqa: TC003
from typing import Any, cast

from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_config_file

from .config import TriggerReplyConfig  # noqa: TC001
from .models import (
    MatchType,
    TriggerEntry,
    TriggerMatch,
    TriggerReply,
    TriggerScene,
)

_rules_cache: tuple[TriggerEntry, ...] | None = None
_rules_cache_count: int = 0


def _load_toml() -> Any:
    try:
        import tomllib as mod
    except ImportError:
        import tomli as mod  # type: ignore[no-redef]
    return mod.loads


def _load_rules(file_path: Path) -> tuple[tuple[TriggerEntry, ...], list[str]]:
    if not file_path.exists():
        logger.warning("触发回复规则文件不存在: {}", file_path)
        return (), [f"规则文件不存在: {file_path}"]
    raw_text = file_path.read_text(encoding="utf-8")
    try:
        payload = _load_toml()(raw_text)
    except Exception as exc:  # noqa: BLE001
        return (), [f"TOML 解析失败: {exc}"]
    if not isinstance(payload, Mapping):
        return (), ["规则文件必须是 TOML 表"]
    entries: list[TriggerEntry] = []
    errors: list[str] = []
    for entry_id, raw_entry in payload.items():
        try:
            entry, entry_errors = _parse_entry(str(entry_id), raw_entry)
            entries.append(entry)
            errors.extend(entry_errors)
        except (TypeError, ValueError) as exc:
            errors.append(f"[{entry_id}]: {exc}")
    entries.sort(key=lambda e: e.priority)
    return tuple(entries), errors


def _parse_entry(entry_id: str, raw: object) -> tuple[TriggerEntry, list[str]]:
    if not isinstance(raw, Mapping):
        msg = "entry must be a table"
        raise TypeError(msg)
    errors: list[str] = []
    match_objects, match_errors = _parse_matches(raw)
    matches = tuple(match_objects)
    errors.extend(match_errors)
    replies_obj, reply_errors = _parse_replies(raw.get("reply"))
    replies = tuple(replies_obj)
    errors.extend(reply_errors)
    if not matches:
        raise ValueError("entry must contain at least one valid match")  # noqa: TRY003
    if not replies:
        raise ValueError("entry must contain at least one reply")  # noqa: TRY003
    scenes = _parse_scene_filter(raw.get("scenes"))
    return TriggerEntry(
        _id=entry_id,
        enabled=_bool_val(raw.get("enabled"), fallback=True),
        priority=_int_val(raw.get("priority"), fallback=1, minimum=1),
        block=_bool_val(raw.get("block"), fallback=True),
        chance=_float_val(raw.get("chance"), fallback=1.0, minimum=0.0, maximum=1.0),
        scenes=scenes,
        groups=_parse_id_filter(raw.get("groups")),
        users=_parse_id_filter(raw.get("users")),
        matches=matches,
        replies=replies,
    ), errors


def _parse_matches(  # noqa: C901
    raw: Mapping[object, object],
) -> tuple[list[TriggerMatch], list[str]]:
    matches: list[TriggerMatch] = []
    errors: list[str] = []
    entry_type = _str_val(raw.get("type"))
    raw_match = raw.get("match")
    if raw_match is not None:
        for item in _list_val(raw_match, strip=False):
            if isinstance(item, str):
                m = _build_match(entry_type, item, raw)
                if m is not None:
                    matches.append(m)
    raw_matches = raw.get("matches")
    if (
        raw_matches is not None
        and isinstance(raw_matches, Sequence)
        and not isinstance(raw_matches, str)
    ):
        for index, item in enumerate(raw_matches):
            try:
                if isinstance(item, Mapping):
                    matches.append(_parse_single_match(item))
                elif isinstance(item, str):
                    mt = _build_match(entry_type, item, raw)
                    if mt is not None:
                        matches.append(mt)
            except (TypeError, ValueError) as exc:
                errors.append(f"matches[{index}]: {exc}")
    return matches, errors


def _build_match(
    entry_type: str | None,
    pattern: str,
    raw: Mapping[object, object],
) -> TriggerMatch | None:
    match_type = _normalize_match_type(entry_type or "full")
    to_me = _bool_val(raw.get("to_me"), fallback=False)
    ignore_case = _bool_val(raw.get("ignore_case"), fallback=True)
    compiled = None
    if match_type == "regex":
        flags = re.IGNORECASE if ignore_case else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return None
    return TriggerMatch(
        _type=match_type,
        pattern=pattern,
        to_me=to_me,
        ignore_case=ignore_case,
        strip=_bool_val(raw.get("strip"), fallback=True),
        allow_plaintext=_bool_val(raw.get("allow_plaintext"), fallback=True),
        compiled_pattern=compiled,
    )


def _parse_single_match(raw: Mapping[object, object]) -> TriggerMatch:
    match_type = _normalize_match_type(_str_val(raw.get("type")) or "full")
    pattern = _str_val(raw.get("match"), strip=False)
    if pattern is None:
        raise ValueError("match requires match text")  # noqa: TRY003
    ignore_case = _bool_val(raw.get("ignore_case"), fallback=True)
    compiled = None
    if match_type == "regex":
        flags = re.IGNORECASE if ignore_case else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc  # noqa: TRY003
    return TriggerMatch(
        _type=match_type,
        pattern=pattern,
        to_me=_bool_val(raw.get("to_me"), fallback=False),
        ignore_case=ignore_case,
        strip=_bool_val(raw.get("strip"), fallback=True),
        allow_plaintext=_bool_val(raw.get("allow_plaintext"), fallback=True),
        compiled_pattern=compiled,
    )


def _parse_replies(raw: object) -> tuple[list[TriggerReply], list[str]]:
    if raw is None:
        return [], []
    if isinstance(raw, str):
        text = _str_val(raw, strip=False)
        return ([TriggerReply(text=text)] if text else []), []
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        if not raw:
            return [], []
        replies: list[TriggerReply] = []
        errors: list[str] = []
        for index, item in enumerate(raw):
            if isinstance(item, str):
                text = _str_val(item, strip=False)
                if text:
                    replies.append(TriggerReply(text=text))
            elif isinstance(item, Mapping):
                text = _str_val(item.get("text"), strip=False)
                weight = _float_val(
                    item.get("weight"),
                    fallback=1.0,
                    minimum=0.001,
                    maximum=None,
                )
                if text:
                    replies.append(TriggerReply(text=text, weight=weight))
                else:
                    errors.append(f"reply[{index}]: requires text")
            else:
                errors.append(f"reply[{index}]: unsupported type")
        return replies, errors
    return [], []


def _parse_scene_filter(raw: object) -> frozenset[TriggerScene]:
    scenes = _list_val(raw)
    valid: set[TriggerScene] = set()
    for s in scenes:
        if s in {"group", "private"}:
            valid.add(cast("TriggerScene", s))
    return frozenset(valid)


def _parse_id_filter(raw: object) -> frozenset[str]:
    candidates = _list_val(raw)
    if not candidates:
        return frozenset()
    if isinstance(raw, Mapping):
        mode = _str_val(raw.get("mode")) or "white"
        if mode not in {"white", "black"}:
            return frozenset()
        candidates = _list_val(raw.get("values"))
    return frozenset(item for item in candidates if _is_scoped_id(item))


def _is_scoped_id(value: str) -> bool:
    platform, separator, target = value.partition(":")
    return bool(platform and separator and target)


def _normalize_match_type(value: str) -> MatchType:
    v = value.lower()
    if v == "exact":
        v = "full"
    if v == "contains":
        v = "fuzzy"
    if v == "startswith":
        v = "start"
    if v == "endswith":
        v = "end"
    if v in {"full", "fuzzy", "start", "end", "regex"}:
        return v  # type: ignore[return-value]
    raise ValueError(f"unsupported match type: {value}")  # noqa: TRY003


def _str_val(value: object, *, strip: bool = True) -> str | None:
    if value is None:
        return None
    text = str(value)
    if strip:
        text = text.strip()
        return text or None
    return text if text.strip() else None


def _list_val(value: object, *, strip: bool = True) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _str_val(value, strip=strip)
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, Mapping):
        result: list[str] = []
        for item in value:
            text = _str_val(item, strip=strip)
            if text:
                result.append(text)
        return result
    text = _str_val(value, strip=strip)
    return [text] if text else []


def _bool_val(value: object, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return fallback


def _int_val(value: object, *, fallback: int, minimum: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        return max(int(value), minimum)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _float_val(
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


def _refresh_rules(config: TriggerReplyConfig) -> tuple[int, list[str]]:
    global _rules_cache, _rules_cache_count  # noqa: PLW0603
    file_path = get_plugin_config_file(config.rules_file)
    entries, errors = _load_rules(file_path)
    _rules_cache = entries
    _rules_cache_count += 1
    count = len(entries)
    if errors:
        logger.warning(
            "触发回复加载了 {} 条规则，{} 个错误: {}",
            count,
            len(errors),
            "; ".join(errors),
        )
    else:
        logger.info("触发回复加载了 {} 条规则", count)
    return count, errors


def _ensure_loaded(config: TriggerReplyConfig) -> tuple[TriggerEntry, ...]:
    global _rules_cache, _rules_cache_count  # noqa: PLW0602
    if _rules_cache is None or _rules_cache_count == 0:
        _refresh_rules(config)
    assert _rules_cache is not None
    return _rules_cache
