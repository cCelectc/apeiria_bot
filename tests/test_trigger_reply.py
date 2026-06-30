from __future__ import annotations

import re


def _mods():
    from apeiria.builtin_plugins.trigger_reply import models, service

    return models, service


def _input(models, **kw: object):
    base = {
        "platform": "qq",
        "bot_id": "b",
        "user_id": "u1",
        "group_id": None,
        "message_text": "",
        "plaintext": "",
        "is_to_me": False,
    }
    base.update(kw)
    return models.TriggerInput(**base)


def _entry(models, *, matches, replies, **kw: object):
    return models.TriggerEntry(_id="e", matches=matches, replies=replies, **kw)


# --------------------------------------------------------------------------
# service._evaluate — match types
# --------------------------------------------------------------------------


def test_full_match_returns_reply() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="full", pattern="hello")
    entry = _entry(models, matches=(match,), replies=(models.TriggerReply(text="hi"),))
    trigger = _input(models, message_text="hello", plaintext="hello")
    assert service._evaluate(trigger, (entry,))[0] == "hi"


def test_non_match_returns_none() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="full", pattern="hello")
    entry = _entry(models, matches=(match,), replies=(models.TriggerReply(text="hi"),))
    trigger = _input(models, message_text="bye", plaintext="bye")
    assert service._evaluate(trigger, (entry,)) is None


def test_fuzzy_match() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="fuzzy", pattern="lo")
    entry = _entry(models, matches=(match,), replies=(models.TriggerReply(text="ok"),))
    trigger = _input(models, message_text="hello", plaintext="hello")
    assert service._evaluate(trigger, (entry,))[0] == "ok"


def test_start_and_end_match() -> None:
    models, service = _mods()
    start = _entry(
        models,
        matches=(models.TriggerMatch(_type="start", pattern="he"),),
        replies=(models.TriggerReply(text="s"),),
    )
    end = _entry(
        models,
        matches=(models.TriggerMatch(_type="end", pattern="lo"),),
        replies=(models.TriggerReply(text="e"),),
    )
    trigger = _input(models, message_text="hello", plaintext="hello")
    assert service._evaluate(trigger, (start,))[0] == "s"
    assert service._evaluate(trigger, (end,))[0] == "e"


def test_regex_match() -> None:
    models, service = _mods()
    match = models.TriggerMatch(
        _type="regex", pattern="h.llo", compiled_pattern=re.compile("h.llo")
    )
    entry = _entry(models, matches=(match,), replies=(models.TriggerReply(text="r"),))
    trigger = _input(models, message_text="hello", plaintext="hello")
    assert service._evaluate(trigger, (entry,))[0] == "r"


# --------------------------------------------------------------------------
# service._evaluate — filters and substitution
# --------------------------------------------------------------------------


def test_to_me_filter_blocks_when_not_to_me() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="full", pattern="hello", to_me=True)
    entry = _entry(models, matches=(match,), replies=(models.TriggerReply(text="hi"),))
    trigger = _input(models, message_text="hello", plaintext="hello", is_to_me=False)
    assert service._evaluate(trigger, (entry,)) is None


def test_scene_filter_blocks_private() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="full", pattern="hello")
    entry = _entry(
        models,
        matches=(match,),
        replies=(models.TriggerReply(text="hi"),),
        scenes=frozenset({"group"}),
    )
    trigger = _input(models, message_text="hello", plaintext="hello", group_id=None)
    assert service._evaluate(trigger, (entry,)) is None


def test_users_filter() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="full", pattern="hello")
    entry = _entry(
        models,
        matches=(match,),
        replies=(models.TriggerReply(text="hi"),),
        users=models.IdFilter(mode="white", values=frozenset({"qq:u1"})),
    )
    allowed = _input(models, message_text="hello", plaintext="hello", user_id="u1")
    blocked = _input(models, message_text="hello", plaintext="hello", user_id="u2")
    assert service._evaluate(allowed, (entry,))[0] == "hi"
    assert service._evaluate(blocked, (entry,)) is None


def test_substitute_placeholders() -> None:
    models, service = _mods()
    match = models.TriggerMatch(_type="full", pattern="hello")
    entry = _entry(
        models,
        matches=(match,),
        replies=(models.TriggerReply(text="hi {user_id}"),),
    )
    trigger = _input(models, message_text="hello", plaintext="hello", user_id="u1")
    assert service._evaluate(trigger, (entry,))[0] == "hi u1"


def test_filter_allows_and_scoped_id() -> None:
    models, service = _mods()
    empty = models.IdFilter(mode="white", values=frozenset())
    assert service._filter_allows(empty, None) is True
    f1 = models.IdFilter(mode="white", values=frozenset({"qq:1"}))
    assert service._filter_allows(f1, None) is False
    assert service._filter_allows(f1, "qq:1") is True
    fstar = models.IdFilter(mode="white", values=frozenset({"qq:*"}))
    assert service._filter_allows(fstar, "qq:5") is True
    assert service._scoped_id(None, "x") is None
    assert service._scoped_id("qq", "1") == "qq:1"


def test_select_reply_single() -> None:
    models, service = _mods()
    assert service._select_reply((models.TriggerReply(text="only"),)) == "only"


# --------------------------------------------------------------------------
# loader — parsing
# --------------------------------------------------------------------------


def test_load_rules_parses_toml(tmp_path) -> None:
    from apeiria.builtin_plugins.trigger_reply import loader

    rules = tmp_path / "rules.toml"
    rules.write_text(
        '[greet]\ntype = "full"\nmatch = "hi"\nreply = "hello"\n', encoding="utf-8"
    )
    entries, errors = loader._load_rules(rules)
    assert errors == []
    assert len(entries) == 1
    assert entries[0].id == "greet"
    assert entries[0].matches
    assert entries[0].replies


def test_load_rules_missing_file() -> None:
    from pathlib import Path

    from apeiria.builtin_plugins.trigger_reply import loader

    entries, errors = loader._load_rules(Path("/no/such/file.toml"))
    assert entries == ()
    assert errors


def test_normalize_match_type_aliases() -> None:
    from apeiria.builtin_plugins.trigger_reply import loader

    assert loader._normalize_match_type("exact") == "full"
    assert loader._normalize_match_type("contains") == "fuzzy"
    assert loader._normalize_match_type("startswith") == "start"
    assert loader._normalize_match_type("endswith") == "end"
    assert loader._normalize_match_type("regex") == "regex"


def test_normalize_match_type_invalid() -> None:
    import pytest

    from apeiria.builtin_plugins.trigger_reply import loader

    with pytest.raises(ValueError, match="unsupported match type"):
        loader._normalize_match_type("nonsense")


def test_is_scoped_id() -> None:
    from apeiria.builtin_plugins.trigger_reply import loader

    assert loader._is_scoped_id("qq:1") is True
    assert loader._is_scoped_id("noseparator") is False
    assert loader._is_scoped_id(":x") is False


def test_parse_replies_variants() -> None:
    from apeiria.builtin_plugins.trigger_reply import loader

    one, errors = loader._parse_replies("hello")
    assert errors == []
    assert len(one) == 1
    assert one[0].text == "hello"

    weighted, errors = loader._parse_replies([{"text": "a", "weight": 2.0}, "b"])
    assert errors == []
    assert {r.text for r in weighted} == {"a", "b"}
