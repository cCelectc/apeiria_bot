from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.access.models import AccessContext, AccessPolicyRule, PluginPolicy
from apeiria.access.permission import PermissionService

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_default_deny_blocks_without_explicit_allow(monkeypatch: MonkeyPatch) -> None:
    _patch_permission_dependencies(
        monkeypatch,
        policy=PluginPolicy(
            plugin_module="plugins.alpha",
            access_mode="default_deny",
            protection_mode="normal",
        ),
    )
    service = PermissionService()

    async def run() -> None:
        decision = await service._evaluate_plugin(
            _context(),
            "plugins.alpha",
        )

        assert decision.allowed is False
        assert decision.code == "access_not_allowed_by_default"
        assert decision.source == "plugin_policy"

    asyncio.run(run())


def test_explicit_allow_admits_only_to_plugin_boundary(
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_permission_dependencies(
        monkeypatch,
        policy=PluginPolicy(
            plugin_module="plugins.alpha",
            access_mode="default_deny",
            protection_mode="normal",
        ),
        rule=AccessPolicyRule(
            subject_type="user",
            subject_id="user-1",
            plugin_module="plugins.alpha",
            effect="allow",
        ),
    )
    service = PermissionService()
    context = _context(is_superuser=False)

    async def run() -> None:
        decision = await service._evaluate_plugin(context, "plugins.alpha")

        assert decision.allowed is True
        assert decision.code == "ok"
        assert context.is_superuser is False

    asyncio.run(run())


def test_explicit_deny_blocks_default_allow(monkeypatch: MonkeyPatch) -> None:
    _patch_permission_dependencies(
        monkeypatch,
        policy=PluginPolicy(
            plugin_module="plugins.alpha",
            access_mode="default_allow",
            protection_mode="normal",
        ),
        rule=AccessPolicyRule(
            subject_type="group",
            subject_id="group-1",
            plugin_module="plugins.alpha",
            effect="deny",
        ),
    )
    service = PermissionService()

    async def run() -> None:
        decision = await service._evaluate_plugin(_context(), "plugins.alpha")

        assert decision.allowed is False
        assert decision.code == "access_denied_by_group_rule"
        assert decision.source == "access_rule"

    asyncio.run(run())


def test_superuser_still_obeys_admission_policy(monkeypatch: MonkeyPatch) -> None:
    _patch_permission_dependencies(
        monkeypatch,
        policy=PluginPolicy(
            plugin_module="plugins.alpha",
            access_mode="default_deny",
            protection_mode="normal",
        ),
    )
    service = PermissionService()

    async def run() -> None:
        decision = await service._evaluate_plugin(
            _context(is_superuser=True),
            "plugins.alpha",
        )

        assert decision.allowed is False
        assert decision.code == "access_not_allowed_by_default"

    asyncio.run(run())


def _context(*, is_superuser: bool = False) -> AccessContext:
    return AccessContext(
        user_id="user-1",
        group_id="group-1",
        conversation_type="group",
        is_superuser=is_superuser,
    )


def _patch_permission_dependencies(
    monkeypatch: MonkeyPatch,
    *,
    policy: PluginPolicy,
    rule: AccessPolicyRule | None = None,
    globally_enabled: bool = True,
) -> None:
    import apeiria.access.permission as permission_module

    monkeypatch.setattr(
        permission_module,
        "plugin_policy_service",
        _FakePluginPolicyService(policy, globally_enabled=globally_enabled),
    )
    monkeypatch.setattr(
        permission_module,
        "access_service",
        _FakeAccessService(rule),
    )


class _FakePluginPolicyService:
    def __init__(
        self,
        policy: PluginPolicy,
        *,
        globally_enabled: bool,
    ) -> None:
        self._policy = policy
        self._globally_enabled = globally_enabled

    async def get_policy(self, plugin_module: str) -> PluginPolicy:
        assert plugin_module == self._policy.plugin_module
        return self._policy

    async def is_globally_enabled(self, plugin_module: str) -> bool:
        assert plugin_module == self._policy.plugin_module
        return self._globally_enabled


class _FakeAccessService:
    def __init__(
        self,
        rule: AccessPolicyRule | None,
    ) -> None:
        self._rule = rule

    async def is_group_bot_enabled(self, group_id: str) -> bool:
        assert group_id == "group-1"
        return True

    async def is_group_plugin_enabled(self, group_id: str, plugin_module: str) -> bool:
        assert group_id == "group-1"
        assert plugin_module == "plugins.alpha"
        return True

    async def get_explicit_rule(
        self,
        context: AccessContext,
        plugin_module: str,
    ) -> AccessPolicyRule | None:
        assert context.user_id == "user-1"
        assert plugin_module == "plugins.alpha"
        return self._rule
