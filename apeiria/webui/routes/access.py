"""Access control routes for plugin admission policy and explicit rules."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from apeiria.access.management import access_management_service
from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.i18n import t
from apeiria.webui.auth import require_auth
from apeiria.webui.routes._deps import require_runtime_control_plane
from apeiria.webui.schemas.models import (
    AccessRuleCreateRequest,
    AccessRuleDeleteRequest,
    AccessRuleItem,
    PluginAccessModeUpdateRequest,
)

router = APIRouter()


@router.get("/rules", response_model=list[AccessRuleItem])
async def list_access_rules(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AccessRuleItem]:
    rows = await require_runtime_control_plane().list_access_rules()
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
    _: Annotated[Any, Depends(require_auth)],
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
        await access_management_service.upsert_access_rule(
            subject_type=body.subject_type,
            subject_id=body.subject_id,
            plugin_module=body.plugin_module,
            effect=body.effect,
            note=body.note,
        )
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
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    deleted = await access_management_service.delete_access_rule(
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
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    if body.access_mode not in {"default_allow", "default_deny"}:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.permissions.invalid_access_mode"),
        )
    try:
        await access_management_service.update_plugin_access_mode(
            module_name,
            access_mode=body.access_mode,
        )
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
    return {"status": "ok"}
