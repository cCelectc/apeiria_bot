from __future__ import annotations

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


def normalize_package_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        return canonicalize_name(Requirement(raw).name)
    except InvalidRequirement:
        return raw
