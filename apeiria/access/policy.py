"""Pure policy helpers for access evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.access.models import AccessContext, AccessPolicyRule


def resolve_explicit_rule(
    context: AccessContext,
    plugin_module: str,
    rules: list[AccessPolicyRule],
) -> AccessPolicyRule | None:
    """Return the highest-priority explicit rule for one context/plugin pair."""
    user_rules = [
        rule
        for rule in rules
        if rule.subject_type == "user"
        and rule.subject_id == context.user_id
        and rule.plugin_module == plugin_module
    ]
    if user_rules:
        return _pick_rule(user_rules)

    if context.group_id is None:
        return None

    group_rules = [
        rule
        for rule in rules
        if rule.subject_type == "group"
        and rule.subject_id == context.group_id
        and rule.plugin_module == plugin_module
    ]
    if group_rules:
        return _pick_rule(group_rules)
    return None


def _pick_rule(rules: list[AccessPolicyRule]) -> AccessPolicyRule:
    denied = [rule for rule in rules if rule.effect == "deny"]
    if denied:
        return denied[0]
    return rules[0]
