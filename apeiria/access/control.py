from __future__ import annotations

from sqlalchemy import select

from apeiria.db.engine import get_db
from apeiria.db.models.access import AccessRule


class AccessControl:
    def __init__(self) -> None:
        self._rules: list[AccessRule] = []
        self._loaded = False

    async def load_snapshot(self) -> None:
        db = get_db()
        async with db.gate.read() as sess:
            rules = list((await sess.execute(select(AccessRule))).scalars().all())
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        self._loaded = True

    def evaluate(self, user_id: str, group_id: str | None, plugin_name: str) -> bool:
        if not self._loaded:
            return True

        from apeiria.utils.superuser import is_superuser_id

        if is_superuser_id(user_id):
            return True

        for rule in self._rules:
            if not _subject_matches(rule, user_id, group_id):
                continue
            if rule.plugin_name is not None and rule.plugin_name != plugin_name:
                continue
            return rule.action == "allow"

        return True

    def evaluate_with_detail(
        self,
        user_id: str,
        group_id: str | None,
        plugin_name: str,
    ) -> dict:
        result: dict = {
            "action": "allow",
            "matched_rule_id": None,
            "matched_rule": None,
        }

        if not self._loaded:
            return result

        from apeiria.utils.superuser import is_superuser_id

        if is_superuser_id(user_id):
            return result

        for rule in self._rules:
            if not _subject_matches(rule, user_id, group_id):
                continue
            if rule.plugin_name is not None and rule.plugin_name != plugin_name:
                continue
            result["action"] = rule.action
            result["matched_rule_id"] = rule.id
            result["matched_rule"] = {
                "id": rule.id,
                "subject_type": rule.subject_type,
                "subject_id": rule.subject_id,
                "plugin_name": rule.plugin_name,
                "action": rule.action,
                "priority": rule.priority,
            }
            break

        return result


def _subject_matches(
    rule: AccessRule,
    user_id: str,
    group_id: str | None,
) -> bool:
    if rule.subject_type == "user":
        return rule.subject_id == user_id
    if rule.subject_type == "group":
        return group_id is not None and rule.subject_id == group_id
    return False
