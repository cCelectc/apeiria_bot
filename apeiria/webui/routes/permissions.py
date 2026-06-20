from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from apeiria.access.management import access_management_service
from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.webui.routes.deps import require_auth
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
    return await access_management_service.list_access_rules()


@router.post("/rules", response_model=AccessRuleItem, status_code=201)
async def create_access_rule(
    body: AccessRuleCreateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AccessRuleItem:
    try:
        await access_management_service.upsert_access_rule(
            subject_type=body.subject_type,
            subject_id=body.subject_id,
            plugin_module=body.plugin_module,
            effect=body.effect,
            note=body.note,
        )
    except ProtectedPluginError:
        raise HTTPException(status_code=400, detail="protected_plugin") from None
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="not_found") from None
    return body


@router.post("/rules/delete")
async def delete_access_rule(
    body: AccessRuleDeleteRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    try:
        success = await access_management_service.delete_access_rule(
            subject_type=body.subject_type,
            subject_id=body.subject_id,
            plugin_module=body.plugin_module,
        )
    except ProtectedPluginError:
        raise HTTPException(status_code=400, detail="protected_plugin") from None
    if not success:
        raise HTTPException(status_code=404, detail="not_found")
    return {"status": "ok"}


@router.patch("/plugins/{module_name}/access-mode")
async def update_plugin_access_mode(
    module_name: str,
    body: PluginAccessModeUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    try:
        await access_management_service.update_plugin_access_mode(
            module_name, access_mode=body.access_mode
        )
    except ProtectedPluginError:
        raise HTTPException(status_code=400, detail="protected_plugin") from None
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="not_found") from None
    return {"status": "ok"}
