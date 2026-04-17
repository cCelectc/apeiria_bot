"""Access control routes — user levels and explicit access rules."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from apeiria.app.access import access_service
from apeiria.app.plugins import plugin_governance_service, plugin_policy_service
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.schemas.models import (
    AccessRuleCreateRequest,
    AccessRuleDeleteRequest,
    AccessRuleItem,
    PluginAccessModeUpdateRequest,
    UpdateLevelRequest,
    UserLevelItem,
)
from apeiria.shared.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.shared.i18n import t

router = APIRouter()


async def _require_manageable_plugin(module_name: str) -> None:
    plugin = await plugin_governance_service.get_plugin(module_name)
    if plugin is None:
        raise ResourceNotFoundError(module_name)
    if plugin.governance_state.kind == "core":
        raise ProtectedPluginError(module_name)


@router.get("/users", response_model=list[UserLevelItem])
async def list_users(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[UserLevelItem]:
    rows = await access_service.list_user_levels()
    return [
        UserLevelItem(user_id=user_id, group_id=group_id, level=level)
        for r in rows
        for user_id, group_id, level in [r]
    ]


@router.patch("/users/{user_id}")
async def update_user_level(
    user_id: str,
    body: UpdateLevelRequest,
    _: Annotated[Any, Depends(require_control_panel)],
    group_id: str = "",
) -> dict[str, str]:
    if not group_id:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.permissions.group_id_required"),
        )

    await access_service.set_user_level(user_id, group_id, body.level)
    return {"status": "ok"}


@router.get("/rules", response_model=list[AccessRuleItem])
async def list_access_rules(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AccessRuleItem]:
    rows = await access_service.list_access_rules()
    return [
        AccessRuleItem(
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            plugin_module=row.plugin_module,
            effect=row.effect,
            note=row.note,
        )
        for row in rows
    ]


@router.post("/rules", response_model=AccessRuleItem)
async def create_access_rule(
    body: AccessRuleCreateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AccessRuleItem:
    if body.subject_type not in {"user", "group"}:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.permissions.invalid_subject"),
        )
    if body.effect not in {"allow", "deny"}:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.permissions.invalid_effect"),
        )
    try:
        await _require_manageable_plugin(body.plugin_module)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_found"),
        ) from None
    except ProtectedPluginError:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.plugins.protected", reason=body.plugin_module),
        ) from None

    await access_service.upsert_access_rule(
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        plugin_module=body.plugin_module,
        effect=body.effect,
        note=body.note,
    )
    return AccessRuleItem(
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        plugin_module=body.plugin_module,
        effect=body.effect,
        note=body.note,
    )


@router.post("/rules/delete")
async def delete_access_rule(
    body: AccessRuleDeleteRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> dict[str, str]:
    deleted = await access_service.delete_access_rule(
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        plugin_module=body.plugin_module,
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.permissions.rule_not_found"),
        )
    return {"status": "ok"}


@router.patch("/plugins/{module_name}/access-mode")
async def update_plugin_access_mode(
    module_name: str,
    body: PluginAccessModeUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> dict[str, str]:
    if body.access_mode not in {"default_allow", "default_deny"}:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.permissions.invalid_access_mode"),
        )
    try:
        await _require_manageable_plugin(module_name)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_found"),
        ) from None
    except ProtectedPluginError:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.plugins.protected", reason=module_name),
        ) from None
    await plugin_policy_service.update_access_mode(
        module_name,
        access_mode=body.access_mode,
    )
    return {"status": "ok"}
