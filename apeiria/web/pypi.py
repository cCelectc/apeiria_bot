from __future__ import annotations

import httpx
from packaging.version import InvalidVersion, Version

_PYPI_BASE = "https://pypi.org/pypi"
_HTTP_OK = 200


def sort_versions(versions: list[str]) -> list[str]:
    valid: list[tuple[Version, str]] = []
    invalid: list[str] = []
    for v in versions:
        try:
            valid.append((Version(v), v))
        except InvalidVersion:
            invalid.append(v)
    valid.sort(key=lambda pair: pair[0], reverse=True)
    invalid.sort(reverse=True)
    return [v for _, v in valid] + invalid


def is_newer(installed: str | None, latest: str | None) -> bool:
    if not installed or not latest:
        return False
    try:
        return Version(latest) > Version(installed)
    except InvalidVersion:
        return False


def _keep_version(files: object) -> bool:
    if not isinstance(files, list) or not files:
        return False
    return any(not (isinstance(f, dict) and f.get("yanked", False)) for f in files)


async def fetch_versions(pkg_base: str) -> list[str] | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_PYPI_BASE}/{pkg_base}/json")
    except httpx.HTTPError:
        return None
    if resp.status_code != _HTTP_OK:
        return None
    try:
        releases = resp.json().get("releases", {})
    except ValueError:
        return None
    if not isinstance(releases, dict):
        return None
    kept = [ver for ver, files in releases.items() if _keep_version(files)]
    return sort_versions(kept)


async def fetch_latest(pkg_base: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_PYPI_BASE}/{pkg_base}/json")
    except httpx.HTTPError:
        return None
    if resp.status_code != _HTTP_OK:
        return None
    try:
        info = resp.json().get("info", {})
    except ValueError:
        return None
    if not isinstance(info, dict):
        return None
    return info.get("version") or None
