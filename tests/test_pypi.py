from __future__ import annotations

from apeiria.web.pypi import is_newer, sort_versions


def test_sort_versions_descending_with_invalid_last() -> None:
    assert sort_versions(["1.0.0", "1.10.0", "1.2.0", "abc"]) == [
        "1.10.0",
        "1.2.0",
        "1.0.0",
        "abc",
    ]


def test_is_newer_true_when_latest_greater() -> None:
    assert is_newer("1.0.0", "1.2.0") is True


def test_is_newer_false_when_equal() -> None:
    assert is_newer("1.2.0", "1.2.0") is False


def test_is_newer_false_when_installed_missing() -> None:
    assert is_newer(None, "1.0.0") is False


def test_is_newer_false_when_latest_missing() -> None:
    assert is_newer("1.0.0", None) is False


def test_is_newer_false_when_unparseable() -> None:
    assert is_newer("x", "y") is False
