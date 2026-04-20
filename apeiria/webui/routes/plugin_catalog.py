"""Plugin catalog and read-only routes."""

from __future__ import annotations

import mimetypes
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from apeiria.exceptions import ResourceNotFoundError
from apeiria.i18n import t
from apeiria.plugins import plugin_governance_service
from apeiria.plugins.store.update_check import (
    plugin_update_check_service,
    supports_plugin_update_check,
)
from apeiria.webui.auth import require_control_panel, require_owner
from apeiria.webui.routes.plugin_support import (
    to_orphan_plugin_config_response,
    to_plugin_item_response,
    to_plugin_readme_response,
    to_plugin_update_check_item,
)
from apeiria.webui.schemas.models import (
    OrphanPluginConfigResponse,
    PluginItem,
    PluginReadmeResponse,
    PluginUpdateCheckItem,
    PluginUpdateCheckRequest,
)

router = APIRouter()


@router.get("/{module_name}/readme", response_model=PluginReadmeResponse)
async def get_plugin_readme(
    module_name: str,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginReadmeResponse:
    try:
        state = await plugin_governance_service.get_plugin_readme(module_name)
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
        asset_path = await plugin_governance_service.get_plugin_readme_asset_path(
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
    plugins = await plugin_governance_service.list_plugins()
    return [
        to_plugin_item_response(
            plugin,
            can_package_update=(
                plugin.governance_state.can_uninstall
                and bool(plugin.package_binding.installed_package)
                and supports_plugin_update_check(
                    plugin.package_binding.installed_package
                )
            ),
        )
        for plugin in plugins
    ]


@router.post("/update-checks", response_model=list[PluginUpdateCheckItem])
async def check_plugin_updates(
    payload: PluginUpdateCheckRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[PluginUpdateCheckItem]:
    plugins = await plugin_governance_service.list_plugins()
    results = await plugin_update_check_service.check_plugins(
        plugins,
        force_refresh=payload.force_refresh,
    )
    return [to_plugin_update_check_item(item) for item in results]


@router.get("/orphan-configs", response_model=OrphanPluginConfigResponse)
async def list_orphan_plugin_configs(
    _: Annotated[Any, Depends(require_owner)],
) -> OrphanPluginConfigResponse:
    items = await plugin_governance_service.list_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)


@router.post("/orphan-configs/cleanup", response_model=OrphanPluginConfigResponse)
async def cleanup_orphan_plugin_configs(
    _: Annotated[Any, Depends(require_owner)],
) -> OrphanPluginConfigResponse:
    items = await plugin_governance_service.cleanup_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)
