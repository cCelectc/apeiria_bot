# ruff: noqa: TC001
from __future__ import annotations

from random import choices, random

from .models import IdFilter, TriggerEntry, TriggerInput, TriggerMatch, TriggerReply


def _platform_alias(adapter_name: str) -> str:
    aliases = {"onebotv11": "qq"}
    return aliases.get(adapter_name, adapter_name)


def _scoped_id(platform: str | None, value: str | None) -> str | None:
    if platform is None or value is None:
        return None
    return f"{platform}:{value}"


def _filter_allows(filter_obj: IdFilter, target: str | None) -> bool:
    if not filter_obj.values:
        return True
    if target is None:
        return False
    matches = target in filter_obj.values
    platform, _, __ = target.partition(":")
    matches = matches or f"{platform}:*" in filter_obj.values
    return matches if filter_obj.mode == "white" else not matches


def _do_match(  # noqa: C901, PLR0911, PLR0912
    trigger: TriggerInput,
    match: TriggerMatch,
) -> str | None:
    if match.to_me and not trigger.is_to_me:
        return None
    pattern = match.pattern
    if pattern is None:
        return None
    message_text = trigger.message_text
    plaintext = trigger.plaintext
    if match.strip:
        message_text = message_text.strip()
        plaintext = plaintext.strip()
        pattern = pattern.strip()
    if match.type == "regex":
        return _match_regex(match, message_text, plaintext)
    cmp_msg = message_text
    cmp_plain = plaintext
    cmp_pattern = pattern
    if match.ignore_case:
        cmp_msg = cmp_msg.lower()
        cmp_plain = cmp_plain.lower()
        cmp_pattern = cmp_pattern.lower()
    if match.type == "full":
        if cmp_msg == cmp_pattern:
            return message_text
        if match.allow_plaintext and cmp_plain == cmp_pattern:
            return plaintext
    elif match.type == "start":
        if cmp_msg.startswith(cmp_pattern):
            return message_text
        if match.allow_plaintext and cmp_plain.startswith(cmp_pattern):
            return plaintext
    elif match.type == "end":
        if cmp_msg.endswith(cmp_pattern):
            return message_text
        if match.allow_plaintext and cmp_plain.endswith(cmp_pattern):
            return plaintext
    else:
        if cmp_pattern in cmp_msg:
            return message_text
        if match.allow_plaintext and cmp_pattern in cmp_plain:
            return plaintext
    return None


def _match_regex(match: TriggerMatch, message_text: str, plaintext: str) -> str | None:
    if match.compiled_pattern is None:
        return None
    m = match.compiled_pattern.search(message_text)
    if m is None and match.allow_plaintext:
        m = match.compiled_pattern.search(plaintext)
    if m is None:
        return None
    return m.group(0)


def _substitute(template: str, trigger: TriggerInput, triggered_text: str) -> str:
    values: dict[str, str] = {
        "user_id": trigger.user_id or "",
        "group_id": trigger.group_id or "",
        "message": trigger.message_text,
        "text": trigger.plaintext,
        "trigger": triggered_text,
        "bot_id": trigger.bot_id or "",
    }
    if trigger.group_id is None:
        values["group_id"] = ""
    try:
        return template.format(**values)
    except Exception:  # noqa: BLE001
        return template


def _select_reply(replies: tuple[TriggerReply, ...]) -> str:
    texts = tuple(r.text for r in replies)
    weights = tuple(r.weight for r in replies)
    return choices(texts, weights=weights, k=1)[0]


def _evaluate(
    trigger: TriggerInput, entries: tuple[TriggerEntry, ...]
) -> tuple[str, TriggerEntry] | None:
    for entry in entries:
        if not entry.enabled:
            continue
        if entry.scenes and trigger.scene not in entry.scenes:
            continue
        if entry.groups and not _filter_allows(
            entry.groups, _scoped_id(trigger.platform, trigger.group_id)
        ):
            continue
        if entry.users and not _filter_allows(
            entry.users, _scoped_id(trigger.platform, trigger.user_id)
        ):
            continue
        triggered_text: str | None = None
        for match in entry.matches:
            triggered_text = _do_match(trigger, match)
            if triggered_text is not None:
                break
        if triggered_text is None:
            continue
        if entry.chance < 1.0 and random() >= entry.chance:
            continue
        reply_template = _select_reply(entry.replies)
        return _substitute(reply_template, trigger, triggered_text), entry
    return None
