"""Plugin catalog and read-only routes."""

from __future__ import annotations

import mimetypes
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from apeiria.app.plugins.management import plugin_management_service
from apeiria.exceptions import ResourceNotFoundError
from apeiria.i18n import t
from apeiria.runtime.context import get_current_runtime
from apeiria.webui.auth import require_control_panel, require_owner
from apeiria.webui.schemas.plugin_catalog import (
    OrphanPluginConfigResponse,
    PluginItem,
    PluginReadmeResponse,
    PluginUpdateCheckItem,
    PluginUpdateCheckRequest,
    PluginWorkspaceResponse,
    to_orphan_plugin_config_response,
    to_plugin_item_response,
    to_plugin_readme_response,
    to_plugin_update_check_item,
)
from apeiria.webui.schemas.plugin_config import to_plugin_workspace_settings_summary
from apeiria.webui.schemas.plugin_management import to_plugin_toggle_preview_response
from apeiria.webui.schemas.plugin_workbench import (
    PluginWorkbenchResponse,
    to_plugin_workbench_response,
)

router = APIRouter()
_RUNTIME_UNAVAILABLE_DETAIL = "Apeiria runtime control plane is unavailable."


def _require_runtime_control_plane() -> Any:
    runtime = get_current_runtime()
    if runtime is None or runtime.control_plane is None:
        raise HTTPException(status_code=503, detail=_RUNTIME_UNAVAILABLE_DETAIL)
    return runtime.control_plane


@router.get("/{module_name}/readme", response_model=PluginReadmeResponse)
async def get_plugin_readme(
    module_name: str,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginReadmeResponse:
    try:
        state = await plugin_management_service.get_plugin_readme(module_name)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.readme_not_found"),
        ) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_readme_response(state)


@router.get("/{module_name}/readme/asset")
async def get_plugin_readme_asset(
    module_name: str,
    path: Annotated[str, Query(min_length=1)],
    _: Annotated[Any, Depends(require_control_panel)],
) -> FileResponse:
    try:
        asset_path = await plugin_management_service.get_plugin_readme_asset_path(
            module_name,
            path,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.readme_not_found"),
        ) from None
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail=t("web_ui.plugins.readme_asset_forbidden"),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    media_type, _ = mimetypes.guess_type(asset_path.name)
    return FileResponse(
        asset_path,
        media_type=media_type or "application/octet-stream",
        filename=asset_path.name,
        headers={
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/", response_model=list[PluginItem])
async def list_plugins(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[PluginItem]:
    control_plane = _require_runtime_control_plane()
    plugins = await control_plane.list_plugin_catalog_entries()
    return [
        to_plugin_item_response(
            plugin,
            can_package_update=control_plane.can_plugin_package_update(plugin),
        )
        for plugin in plugins
    ]


@router.get("/workbench", response_model=PluginWorkbenchResponse)
async def get_plugin_workbench(
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginWorkbenchResponse:
    control_plane = _require_runtime_control_plane()
    workspace = await control_plane.get_plugin_workbench()
    return to_plugin_workbench_response(workspace)


@router.get("/{module_name}/workspace", response_model=PluginWorkspaceResponse)
async def get_plugin_workspace(
    module_name: str,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginWorkspaceResponse:
    workspace = await plugin_management_service.build_plugin_workspace(module_name)
    if workspace is None:
        raise HTTPException(status_code=404, detail=t("web_ui.plugins.not_found"))

    plugin_item = to_plugin_item_response(
        workspace.plugin,
        can_package_update=workspace.can_package_update,
    )
    enable_preview = (
        to_plugin_toggle_preview_response(workspace.enable_preview)
        if workspace.enable_preview is not None
        else None
    )
    disable_preview = (
        to_plugin_toggle_preview_response(workspace.disable_preview)
        if workspace.disable_preview is not None
        else None
    )
    settings = (
        to_plugin_workspace_settings_summary(workspace.settings)
        if workspace.settings is not None
        else None
    )

    return PluginWorkspaceResponse(
        plugin=plugin_item,
        enable_preview=enable_preview,
        disable_preview=disable_preview,
        settings=settings,
        readme_available=plugin_item.can_view_readme,
    )


@router.post("/update-checks", response_model=list[PluginUpdateCheckItem])
async def check_plugin_updates(
    payload: PluginUpdateCheckRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[PluginUpdateCheckItem]:
    results = await plugin_management_service.check_plugin_updates(
        force_refresh=payload.force_refresh,
    )
    return [to_plugin_update_check_item(item) for item in results]


@router.get("/orphan-configs", response_model=OrphanPluginConfigResponse)
async def list_orphan_plugin_configs(
    _: Annotated[Any, Depends(require_owner)],
) -> OrphanPluginConfigResponse:
    items = await plugin_management_service.list_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)


@router.post("/orphan-configs/cleanup", response_model=OrphanPluginConfigResponse)
async def cleanup_orphan_plugin_configs(
    _: Annotated[Any, Depends(require_owner)],
) -> OrphanPluginConfigResponse:
    items = await plugin_management_service.cleanup_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)
