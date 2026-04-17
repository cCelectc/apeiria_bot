"""Application-facing permission service."""

from __future__ import annotations

from nonebot.exception import IgnoredException
from nonebot.log import logger

from apeiria.app.access.models import AccessContext, PermissionDecision, PluginPolicy
from apeiria.app.access.service import access_service
from apeiria.app.plugins import plugin_policy_service
from apeiria.shared.i18n import t


class PermissionService:
    """Evaluate runtime permission decisions for plugin execution."""

    async def check_plugin_execution(self, bot, event, plugin) -> PermissionDecision:  # noqa: ANN001
        context = await access_service.build_context(bot, event)
        if context is None:
            return self._allow()

        plugin_module = plugin.module_name  # type: ignore[attr-defined]
        policy = await plugin_policy_service.get_policy(plugin_module)
        decision = await self._check_plugin_state(context.group_id, policy)
        if decision is not None:
            return decision

        if context.is_superuser:
            return self._allow()

        decision = await self._check_access_rules(
            context,
            plugin_module,
            policy.access_mode,
        )
        if decision is not None:
            return decision

        effective_level = await access_service.get_effective_level(context)
        if effective_level >= policy.required_level:
            return self._allow()

        logger.debug(
            "Access denied by level: user={} plugin={} need={} have={}",
            context.user_id,
            plugin_module,
            policy.required_level,
            effective_level,
        )
        return PermissionDecision(
            allowed=False,
            code="insufficient_level",
            reason=t("auth.permission_denied", need=f"Lv.{policy.required_level}"),
            source="required_level",
            details={
                "required_level": policy.required_level,
                "effective_level": effective_level,
            },
        )

    async def assert_plugin_allowed(self, bot, event, plugin) -> None:  # noqa: ANN001
        from apeiria.interfaces.bot.feedback import guard_feedback_service

        decision = await self.check_plugin_execution(bot, event, plugin)
        if decision.allowed:
            return
        await guard_feedback_service.handle_denied(bot, event, decision)
        raise IgnoredException(decision.code)

    async def _check_plugin_state(
        self,
        group_id: str | None,
        policy: PluginPolicy,
    ) -> PermissionDecision | None:
        is_enabled = await plugin_policy_service.is_globally_enabled(
            policy.plugin_module
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
            reason=t("auth.plugin_disabled"),
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
                    reason=t("auth.access_not_allowed"),
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


permission_service = PermissionService()
