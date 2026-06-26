"""Semver parsing, output sanitization, and git command helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.system.project_update.models import (
    _OUTPUT_EXCERPT_LIMIT,
    _SECRET_VALUE_RE,
    _SEMVER_TAG_RE,
    _URL_CREDENTIAL_RE,
    SemverTag,
)

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Sequence


def parse_semver_tag(tag: str) -> SemverTag | None:
    match = _SEMVER_TAG_RE.match(tag.strip())
    if match is None:
        return None
    prerelease = tuple(
        part for part in (match.group("prerelease") or "").split(".") if part
    )
    version = (
        f"{match.group('major')}.{match.group('minor')}.{match.group('patch')}"
        f"{('-' + '.'.join(prerelease)) if prerelease else ''}"
    )
    return SemverTag(
        raw=tag,
        normalized=version,
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=prerelease,
        build=match.group("build"),
    )


def sanitize_output(value: str) -> str:
    sanitized = _URL_CREDENTIAL_RE.sub(r"\1***@", value)
    return _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=***", sanitized)


def _compare_semver(left: SemverTag, right: SemverTag) -> int:
    left_key = _semver_sort_key(left)
    right_key = _semver_sort_key(right)
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


def _semver_sort_key(value: SemverTag | None) -> tuple[object, ...]:
    if value is None:
        return (-1, -1, -1, -1)
    return (
        value.major,
        value.minor,
        value.patch,
        1 if not value.prerelease else 0,
        _prerelease_sort_key(value.prerelease),
    )


def _prerelease_sort_key(parts: tuple[str, ...]) -> tuple[tuple[int, object], ...]:
    key: list[tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return tuple(key)


def _bounded_output(stdout: str | None, stderr: str | None) -> str:
    output = "\n".join(
        part.strip() for part in (stdout, stderr) if part and part.strip()
    )
    if len(output) <= _OUTPUT_EXCERPT_LIMIT:
        return output
    return output[-_OUTPUT_EXCERPT_LIMIT:]


def _command_error(
    args: Sequence[str],
    result: subprocess.CompletedProcess[str],
) -> str:
    output = sanitize_output(_bounded_output(result.stdout, result.stderr))
    summary = sanitize_output(" ".join(["git", *args]))
    if output:
        return f"{summary} failed with status {result.returncode}\n{output}"
    return f"{summary} failed with status {result.returncode}"
