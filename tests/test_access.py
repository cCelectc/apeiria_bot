from __future__ import annotations

from types import SimpleNamespace

import pytest


def _rule(subject_type, subject_id, action, *, plugin_name=None, priority=0):
    from apeiria.db.models.access import AccessRule

    return AccessRule(
        subject_type=subject_type,
        subject_id=subject_id,
        plugin_name=plugin_name,
        action=action,
        priority=priority,
    )


def _control(rules, *, loaded=True):
    from apeiria.access.control import AccessControl

    ac = AccessControl()
    ac._loaded = loaded
    ac._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
    return ac


def _no_superuser(monkeypatch) -> None:
    monkeypatch.setattr("apeiria.access.control._is_superuser", lambda _uid: False)


# --------------------------------------------------------------------------
# FR1 — AccessControl.evaluate
# --------------------------------------------------------------------------


def test_evaluate_not_loaded_allows() -> None:
    from apeiria.access.control import AccessControl

    assert AccessControl().evaluate("u1", None, "p") is True


def test_evaluate_superuser_bypasses_deny(monkeypatch) -> None:
    monkeypatch.setattr(
        "apeiria.access.control._is_superuser", lambda uid: uid == "boss"
    )
    ac = _control([_rule("user", "boss", "deny")])
    assert ac.evaluate("boss", None, "p") is True


def test_evaluate_no_matching_rule_allows(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    assert _control([]).evaluate("u1", None, "p") is True


def test_evaluate_user_allow(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    ac = _control([_rule("user", "u1", "allow")])
    assert ac.evaluate("u1", None, "p") is True


def test_evaluate_user_deny(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    ac = _control([_rule("user", "u1", "deny")])
    assert ac.evaluate("u1", None, "p") is False


def test_evaluate_group_deny_only_matching_group(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    ac = _control([_rule("group", "g1", "deny")])
    assert ac.evaluate("u1", "g1", "p") is False
    assert ac.evaluate("u1", "g2", "p") is True
    assert ac.evaluate("u1", None, "p") is True


def test_evaluate_higher_priority_wins(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    ac = _control(
        [
            _rule("user", "u1", "deny", priority=1),
            _rule("user", "u1", "allow", priority=5),
        ]
    )
    assert ac.evaluate("u1", None, "p") is True


def test_evaluate_plugin_scoped_rule(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    ac = _control([_rule("user", "u1", "deny", plugin_name="repeater")])
    assert ac.evaluate("u1", None, "repeater") is False
    assert ac.evaluate("u1", None, "help") is True


def test_evaluate_none_plugin_applies_to_all(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    ac = _control([_rule("user", "u1", "deny", plugin_name=None)])
    assert ac.evaluate("u1", None, "anything") is False


# --------------------------------------------------------------------------
# FR2 — access_preprocessor hook (function level, no test_matcher)
# --------------------------------------------------------------------------


def _session(user_id, *, is_group, scene_id="s"):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        scene=SimpleNamespace(is_group=is_group, id=scene_id),
    )


def test_resolve_subject_group_and_private() -> None:
    from apeiria.access.hook import resolve_subject

    assert resolve_subject(_session("u1", is_group=True, scene_id="g1")) == ("u1", "g1")
    assert resolve_subject(_session("u1", is_group=False)) == ("u1", None)


async def test_access_preprocessor_blocks_on_deny(monkeypatch) -> None:
    from nonebot.exception import IgnoredException

    from apeiria.access import hook

    monkeypatch.setattr(hook, "check_access", lambda *_: False)
    matcher = SimpleNamespace(plugin_name="repeater")
    with pytest.raises(IgnoredException):
        await hook.access_preprocessor(matcher, _session("u1", is_group=False))


async def test_access_preprocessor_passes_on_allow(monkeypatch) -> None:
    from apeiria.access import hook

    monkeypatch.setattr(hook, "check_access", lambda *_: True)
    matcher = SimpleNamespace(plugin_name="repeater")
    await hook.access_preprocessor(matcher, _session("u1", is_group=False))


def test_check_access_delegates_to_evaluate(monkeypatch) -> None:
    _no_superuser(monkeypatch)
    from apeiria.access import hook

    ac = _control([_rule("user", "u1", "deny")])
    monkeypatch.setattr("apeiria.bootstrap.steps.get_access_control", lambda: ac)
    assert hook.check_access("p", "u1", None) is False


def test_check_access_superuser_passes(monkeypatch) -> None:
    monkeypatch.setattr("apeiria.access.control._is_superuser", lambda _uid: True)
    from apeiria.access import hook

    ac = _control([_rule("user", "u1", "deny")])
    monkeypatch.setattr("apeiria.bootstrap.steps.get_access_control", lambda: ac)
    assert hook.check_access("p", "u1", None) is True
