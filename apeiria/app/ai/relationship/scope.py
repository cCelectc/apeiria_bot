"""Pure helpers for relationship scope normalization."""

from __future__ import annotations


def build_affinity_scope_key(group_id: str | None) -> str:
    """Build a non-null scope key for affinity uniqueness."""

    if group_id is None:
        return "private"
    return f"group:{group_id}"
