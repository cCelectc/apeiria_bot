"""Application-facing permission service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.access.audit import AuditActor
from apeiria.access.audit_service import audit_service
from apeiria.access.models import AccessContext, PermissionDecision, PluginPolicy
from apeiria.access.service import access_service

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class PermissionService:
    """Evaluate runtime permission decisions for plugin execution."""

    def __init__(self) -> None:
        self._get_policy: "Callable[[str], Awaitable[PluginPolicy]] | None" = None
        self._is_globally_enabled: "Callable[[str], Awaitable[bool]] | None" = None

    def wire(
        self,
        *,
        get_policy: "Callable[[str], Awaitable[PluginPolicy]]",
        is_globally_enabled: "Callable[[str], Awaitable[bool]]",
    ) -> None:
        self._get_policy = get_policy
        self._is_globally_enabled = is_globally_enabled

    async def check_plugin_execution(
        self,
        context: AccessContext,
        *,
        plugin_module: str,
    ) -> PermissionDecision:
        decision = await self._evaluate_plugin(context, plugin_module)
        self._emit_diagnostic(plugin_module, decision)
        return decision

    def allow(self) -> PermissionDecision:
        """Return the default allow decision for contexts that cannot be built."""

        return self._allow()

    async def _evaluate_plugin(
        self,
        context: AccessContext,
        plugin_module: str,
    ) -> PermissionDecision:
        if context.is_superuser:
            return self._allow()
        if self._get_policy is None:
            return self._allow()
        policy = await self._get_policy(plugin_module)
        decision = await self._check_plugin_state(context.group_id, policy)
        if decision is not None:
            return decision

        decision = await self._check_access_rules(
            context,
            plugin_module,
            policy.access_mode,
        )
        if decision is not None:
            return decision
        return self._allow()

    async def _check_plugin_state(
        self,
        group_id: str | None,
        policy: PluginPolicy,
    ) -> PermissionDecision | None:
        is_enabled = (
            await self._is_globally_enabled(policy.plugin_module)
            if self._is_globally_enabled
            else True
        )
        if policy.protection_mode != "required" and not is_enabled:
            return PermissionDecision(
                allowed=False,
                code="plugin_globally_disabled",
                source="plugin_policy",
            )

        if group_id is None:
            return None
        if not await access_service.is_group_bot_enabled(group_id):
            return PermissionDecision(
                allowed=False,
                code="bot_disabled_in_group",
                source="group_runtime_state",
            )
        if await access_service.is_group_plugin_enabled(group_id, policy.plugin_module):
            return None
        return PermissionDecision(
            allowed=False,
            code="plugin_disabled_in_group",
            reason="plugin_disabled_in_group",
            source="group_plugin_state",
        )

    async def _check_access_rules(
        self,
        context: AccessContext,
        plugin_module: str,
        access_mode: str,
    ) -> PermissionDecision | None:
        explicit_rule = await access_service.get_explicit_rule(context, plugin_module)
        if explicit_rule is None:
            if access_mode == "default_deny":
                return PermissionDecision(
                    allowed=False,
                    code="access_not_allowed_by_default",
                    reason="access_not_allowed_by_default",
                    source="plugin_policy",
                )
            return None
        if explicit_rule.effect != "deny":
            return None
        return PermissionDecision(
            allowed=False,
            code=(
                "access_denied_by_user_rule"
                if explicit_rule.subject_type == "user"
                else "access_denied_by_group_rule"
            ),
            source="access_rule",
            details={
                "subject_type": explicit_rule.subject_type,
                "subject_id": explicit_rule.subject_id,
                "plugin_module": explicit_rule.plugin_module,
            },
        )

    def _allow(self) -> PermissionDecision:
        return PermissionDecision(allowed=True, code="ok", source="runtime")

    def _emit_diagnostic(
        self,
        plugin_module: str,
        decision: PermissionDecision,
    ) -> None:
        if decision.allowed:
            return
        audit_service.record(
            "permission.denied",
            actor=self._audit_actor_for_decision(decision),
            target_kind="plugin",
            target_id=plugin_module,
            outcome="failed",
            detail=decision.code,
            metadata={
                "source": decision.source,
                "details": decision.details,
            },
        )

    @staticmethod
    def _audit_actor_for_decision(decision: PermissionDecision) -> AuditActor | None:
        details = decision.details or {}
        subject_id = details.get("subject_id")
        if not isinstance(subject_id, str) or not subject_id:
            return None
        subject_type = details.get("subject_type")
        actor_kind = "adapter_user" if subject_type == "user" else "adapter_group"
        return AuditActor(
            actor_kind=actor_kind,
            actor_id=subject_id,
            display_name=subject_id,
        )


permission_service = PermissionService()
