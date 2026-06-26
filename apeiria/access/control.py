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
