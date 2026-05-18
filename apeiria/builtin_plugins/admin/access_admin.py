"""Owner-facing access control commands."""

from __future__ import annotations

from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna

from apeiria.app.access.management import access_management_service
from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.i18n import t

from .presenter import render_block
from .utils import ensure_owner_message, resolve_plugin_catalog_query

_access = on_alconna(
    Alconna(
        "access",
        Args["action", str],
        Args["arg1?", str],
        Args["arg2?", str],
        Args["arg3?", str],
        Args["arg4?", str],
        meta=CommandMeta(description=t("admin.command.access")),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_access.handle()
async def handle_access(  # noqa: PLR0913
    event: Event,
    action: Match[str],
    arg1: Match[str],
    arg2: Match[str],
    arg3: Match[str],
    arg4: Match[str],
) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _access.finish(owner_error)

    selected_action = action.result.strip().lower()
    if selected_action == "plugin":
        if not arg1.available:
            await _access.finish(t("admin.access.plugin_usage"))
        await _access.finish(await _render_plugin_access(arg1.result))

    if selected_action == "rule":
        if not (
            arg1.available and arg2.available and arg3.available and arg4.available
        ):
            await _access.finish(t("admin.access.rule_usage"))
        await _access.finish(
            await _upsert_rule(
                effect=arg1.result,
                subject_type=arg2.result,
                subject_id=arg3.result,
                plugin_query=arg4.result,
            )
        )

    if selected_action == "remove":
        if not (arg1.available and arg2.available and arg3.available):
            await _access.finish(t("admin.access.remove_usage"))
        await _access.finish(
            await _delete_rule(
                subject_type=arg1.result,
                subject_id=arg2.result,
                plugin_query=arg3.result,
            )
        )

    await _access.finish(t("admin.access.invalid_action"))


async def _render_plugin_access(plugin_query: str) -> str:
    item, candidates = await resolve_plugin_catalog_query(
        plugin_query,
        allow_fuzzy=True,
    )
    if candidates:
        return t(
            "admin.plugin.ambiguous",
            name=plugin_query,
            candidates=", ".join(candidates),
        )
    if item is None:
        return t("admin.plugin.not_found", name=plugin_query)

    module_name = item.descriptor.module_name
    try:
        summary = await access_management_service.get_plugin_access_summary(module_name)
    except ResourceNotFoundError:
        return t("admin.plugin.not_found", name=plugin_query)

    return render_block(
        t("admin.access.plugin_title", name=item.descriptor.name),
        [
            (t("admin.plugin.field_module"), module_name),
            (t("admin.plugin.field_kind"), item.governance_state.kind),
            (t("admin.access.field_access_mode"), summary.access_mode),
            (t("admin.access.field_user_allow"), summary.user_allow_count),
            (t("admin.access.field_user_deny"), summary.user_deny_count),
            (t("admin.access.field_group_allow"), summary.group_allow_count),
            (t("admin.access.field_group_deny"), summary.group_deny_count),
            (t("admin.access.field_disabled_groups"), summary.disabled_group_count),
        ],
        summary=item.descriptor.description or t("admin.plugin.no_description"),
        footer=t(
            "admin.access.plugin_footer",
            module=module_name,
        ),
    )


async def _upsert_rule(
    *,
    effect: str,
    subject_type: str,
    subject_id: str,
    plugin_query: str,
) -> str:
    normalized_effect = effect.strip().lower()
    normalized_subject_type = subject_type.strip().lower()
    if normalized_effect not in {"allow", "deny"} or normalized_subject_type not in {
        "user",
        "group",
    }:
        return t("admin.access.rule_usage")

    item, candidates = await resolve_plugin_catalog_query(
        plugin_query,
        allow_fuzzy=True,
    )
    if candidates:
        return t(
            "admin.plugin.ambiguous",
            name=plugin_query,
            candidates=", ".join(candidates),
        )
    if item is None:
        return t("admin.plugin.not_found", name=plugin_query)

    try:
        await access_management_service.upsert_access_rule(
            subject_type=normalized_subject_type,
            subject_id=subject_id.strip(),
            plugin_module=item.descriptor.module_name,
            effect=normalized_effect,
        )
    except ResourceNotFoundError:
        return t("admin.plugin.not_found", name=plugin_query)
    except ProtectedPluginError as exc:
        return t("admin.plugin.protected", name=item.descriptor.name, reason=str(exc))
    return t(
        "admin.access.rule_updated",
        effect=normalized_effect,
        subject_type=normalized_subject_type,
        subject_id=subject_id.strip(),
        plugin=item.descriptor.name,
    )


async def _delete_rule(
    *,
    subject_type: str,
    subject_id: str,
    plugin_query: str,
) -> str:
    normalized_subject_type = subject_type.strip().lower()
    if normalized_subject_type not in {"user", "group"}:
        return t("admin.access.remove_usage")

    item, candidates = await resolve_plugin_catalog_query(
        plugin_query,
        allow_fuzzy=True,
    )
    if candidates:
        return t(
            "admin.plugin.ambiguous",
            name=plugin_query,
            candidates=", ".join(candidates),
        )
    if item is None:
        return t("admin.plugin.not_found", name=plugin_query)

    deleted = await access_management_service.delete_access_rule(
        subject_type=normalized_subject_type,
        subject_id=subject_id.strip(),
        plugin_module=item.descriptor.module_name,
    )
    if not deleted:
        return t("admin.access.rule_not_found")
    return t(
        "admin.access.rule_removed",
        subject_type=normalized_subject_type,
        subject_id=subject_id.strip(),
        plugin=item.descriptor.name,
    )
