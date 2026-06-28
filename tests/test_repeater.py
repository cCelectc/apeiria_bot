from __future__ import annotations


def _svc():
    from apeiria.builtin_plugins.repeater.service import RepeaterService

    return RepeaterService()


def _cfg(*, probability=1.0, cooldown_seconds=0, repeat_threshold=2):
    from apeiria.builtin_plugins.repeater.config import RepeaterConfig

    return RepeaterConfig(
        probability=probability,
        cooldown_seconds=cooldown_seconds,
        repeat_threshold=repeat_threshold,
    )


def test_threshold_reached_triggers() -> None:
    svc = _svc()
    cfg = _cfg(repeat_threshold=2)
    assert svc.evaluate("g", "h", "msg", "u1", config=cfg) is None
    assert svc.evaluate("g", "h", "msg", "u2", config=cfg) == "msg"


def test_same_user_consecutive_does_not_repeat() -> None:
    svc = _svc()
    cfg = _cfg(repeat_threshold=2)
    assert svc.evaluate("g", "h", "msg", "u1", config=cfg) is None
    assert svc.evaluate("g", "h", "msg", "u1", config=cfg) is None


def test_different_content_resets() -> None:
    svc = _svc()
    cfg = _cfg(repeat_threshold=2)
    assert svc.evaluate("g", "h1", "a", "u1", config=cfg) is None
    assert svc.evaluate("g", "h2", "b", "u2", config=cfg) is None


def test_probability_zero_never_triggers() -> None:
    svc = _svc()
    cfg = _cfg(probability=0.0, repeat_threshold=2)
    assert svc.evaluate("g", "h", "msg", "u1", config=cfg) is None
    assert svc.evaluate("g", "h", "msg", "u2", config=cfg) is None


def test_cooldown_blocks_repeat() -> None:
    svc = _svc()
    cfg = _cfg(cooldown_seconds=10**9, repeat_threshold=2)
    assert svc.evaluate("g", "h", "msg", "u1", config=cfg) is None
    assert svc.evaluate("g", "h", "msg", "u2", config=cfg) is None


def test_reset_clears_state() -> None:
    svc = _svc()
    cfg = _cfg(repeat_threshold=2)
    assert svc.evaluate("g", "h", "msg", "u1", config=cfg) is None
    svc.reset("g")
    assert svc.evaluate("g", "h", "msg", "u2", config=cfg) is None


def test_hash_message_stable() -> None:
    from apeiria.builtin_plugins.repeater.service import hash_message

    assert hash_message("x") == hash_message("x")
    assert hash_message("x") != hash_message("y")
