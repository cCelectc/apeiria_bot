from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from apeiria.config.loader import load_config, update_runtime_config
from apeiria.config.models import ApeiriaConfig
from apeiria.config.reflector import reflect_model
from apeiria.plugin.adapter_manager import (
    set_adapter_state,
)
from apeiria.plugin.adapter_scanner import scan_adapters
from apeiria.plugin.manager import set_plugin_state
from apeiria.plugin.metadata.resolver import resolve_config_namespace_contract
from apeiria.plugin.scanner import scan_plugins
from apeiria.web.auth import verify_token
from apeiria.web.plugin_metadata import merge_plugin_metadata
from apeiria.web.store import get_status, get_store, paginate
from apeiria.web.tasks import get_task_runner

router = APIRouter(prefix="/api", dependencies=[Depends(verify_token)])


def _write_yaml(raw: dict) -> None:
    import yaml

    p = Path("data/config.yaml")
    p.write_text(
        yaml.dump(raw, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


@router.get("/plugins/list")
async def api_plugins_list() -> JSONResponse:
    import nonebot

    from apeiria.plugin.dependency_graph import get_cached_graph

    metadata_map: dict[str, dict] = {}
    loaded_plugins = nonebot.get_loaded_plugins()
    for plugin in loaded_plugins:
        meta = plugin.metadata
        if meta is None:
            continue
        adapters = meta.supported_adapters
        metadata_map[plugin.name] = {
            "name": meta.name,
            "description": meta.description,
            "usage": meta.usage,
            "type": meta.type,
            "homepage": meta.homepage,
            "supported_adapters": sorted(adapters) if adapters else None,
        }

    dep_graph_obj = get_cached_graph(loaded_plugins)

    items = merge_plugin_metadata(
        scan_plugins(),
        metadata_map,
        dep_graph=dep_graph_obj.graph,
        dep_reverse=dep_graph_obj.reverse,
    )

    scanned_names = {m.name for m in scan_plugins()}
    for plugin in loaded_plugins:
        if plugin.name in scanned_names:
            continue
        if not plugin.metadata and plugin.module_name.startswith("nonebot."):
            continue

        meta = metadata_map.get(plugin.name, {})
        items.append(
            {
                "name": plugin.name,
                "source": "dependency",
                "enabled": True,
                "path_or_module": plugin.module_name,
                "module": plugin.module_name,
                "display_name": meta.get("name"),
                "description": meta.get("description"),
                "usage": meta.get("usage"),
                "type": meta.get("type"),
                "homepage": meta.get("homepage"),
                "supported_adapters": meta.get("supported_adapters"),
                "can_disable": False,
                "can_uninstall": False,
                "depends_on": sorted(dep_graph_obj.graph.get(plugin.name, set())),
                "depended_by": sorted(dep_graph_obj.reverse.get(plugin.name, set())),
            }
        )

    return JSONResponse(content={"plugins": items})


@router.post("/plugins/install")
async def api_plugins_install(data: dict) -> JSONResponse:
    name = data.get("name", "")
    pkg = data.get("pkg", "")
    if not name or not pkg:
        raise HTTPException(status_code=400, detail="name and pkg required")
    task_id = await get_task_runner().start("plugin", name, pkg)
    return JSONResponse(content={"task_id": task_id})


@router.post("/plugins/uninstall")
async def api_plugins_uninstall(data: dict) -> JSONResponse:
    name = data.get("name", "")
    keep_config = data.get("keep_config", False)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    task_id = await get_task_runner().start(
        "plugin", name, name, uninstall=True, keep_config=keep_config
    )
    return JSONResponse(content={"task_id": task_id})


@router.post("/plugins/state")
async def api_plugins_state(data: dict) -> JSONResponse:
    name = data.get("name", "")
    enabled = data.get("enabled", True)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    ok = set_plugin_state(name, enabled)
    return JSONResponse(content={"ok": ok})


@router.get("/plugins/{name}/config")
async def api_plugin_config(name: str) -> JSONResponse:
    contract = resolve_config_namespace_contract(name)

    if contract.source == "none" and not contract.fields:
        raise HTTPException(status_code=404, detail="No config for this plugin")

    app = load_config("data/config.yaml")
    values = app.plugins.get(name, {})
    return JSONResponse(content={**contract.to_dict(), "values": values})


@router.get("/adapters/list")
async def api_adapters_list() -> JSONResponse:
    items = [
        {
            "name": a.name,
            "source": a.source,
            "enabled": a.enabled,
            "module_name": a.module_name,
        }
        for a in scan_adapters()
    ]
    return JSONResponse(content={"adapters": items})


@router.post("/adapters/install")
async def api_adapters_install(data: dict) -> JSONResponse:
    name = data.get("name", "")
    pkg = data.get("pkg", "")
    module_name = data.get("module_name", "")
    if not name or not pkg or not module_name:
        raise HTTPException(
            status_code=400, detail="name, pkg and module_name required"
        )
    task_id = await get_task_runner().start(
        "adapter", name, pkg, module_name=module_name
    )
    return JSONResponse(content={"task_id": task_id})


@router.post("/adapters/uninstall")
async def api_adapters_uninstall(data: dict) -> JSONResponse:
    name = data.get("name", "")
    keep_config = data.get("keep_config", False)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    task_id = await get_task_runner().start(
        "adapter", name, name, uninstall=True, keep_config=keep_config
    )
    return JSONResponse(content={"task_id": task_id})


@router.post("/adapters/state")
async def api_adapters_state(data: dict) -> JSONResponse:
    name = data.get("name", "")
    enabled = data.get("enabled", True)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    ok = set_adapter_state(name, enabled)
    return JSONResponse(content={"ok": ok})


@router.get("/adapters/{name}/config")
async def api_adapter_config(name: str) -> JSONResponse:
    from apeiria.plugin.adapter_resolver import resolve_adapter_config

    contract = resolve_adapter_config(name)
    if contract is None:
        raise HTTPException(status_code=404, detail="No config for this adapter")

    app = load_config("data/config.yaml")
    values = app.adapters.get(name, {})
    return JSONResponse(content={**contract.to_dict(), "values": values})


@router.get("/config")
async def api_config_get() -> JSONResponse:
    app = load_config("data/config.yaml")
    return JSONResponse(content=app.model_dump())


@router.get("/config/schema/{section}")
async def api_config_schema(section: str) -> JSONResponse:
    if section == "nonebot":
        from nonebot import get_driver

        config_cls = get_driver().config.__class__
        fields = reflect_model(config_cls)
        internal_keys = {
            "_env_file",
            "_env_file_encoding",
            "_env_nested_delimiter",
            "api_timeout",
            "session_expire_timeout",
        }
        immutable_keys = {"driver"}
        for f in fields:
            if f.key in immutable_keys:
                f.immutable = True
        fields = [f for f in fields if f.key not in internal_keys]
        try:
            json_schema = config_cls.model_json_schema()
        except (TypeError, ValueError):
            json_schema = {}
        contract = {
            "namespace": None,
            "is_scoped": False,
            "owner_kind": "nonebot",
            "owner_id": "nonebot",
            "source": "pydantic",
            "fields": [f.to_dict() for f in fields],
            "json_schema": json_schema,
        }
    elif section == "apeiria":
        fields = reflect_model(ApeiriaConfig)
        try:
            json_schema = ApeiriaConfig.model_json_schema()
        except (TypeError, ValueError):
            json_schema = {}
        contract = {
            "namespace": None,
            "is_scoped": False,
            "owner_kind": "apeiria",
            "owner_id": "apeiria",
            "source": "pydantic",
            "fields": [f.to_dict() for f in fields],
            "json_schema": json_schema,
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown section: {section}")

    return JSONResponse(content=contract)


@router.put("/config/nonebot")
async def api_config_nonebot(data: dict) -> JSONResponse:
    immutable = {"driver"}
    if blocked := immutable & data.keys():
        raise HTTPException(
            status_code=422,
            detail=f"Cannot modify protected config: {', '.join(sorted(blocked))}",
        )
    _patch_config("nonebot", data)
    return JSONResponse(content={"ok": True})


@router.put("/config/plugins")
async def api_config_plugins(data: dict) -> JSONResponse:
    _patch_config("plugins", data)
    app = load_config("data/config.yaml")
    update_runtime_config(app)
    return JSONResponse(content={"ok": True})


@router.put("/config/adapters")
async def api_config_adapters(data: dict) -> JSONResponse:
    _patch_config("adapters", data)
    app = load_config("data/config.yaml")
    update_runtime_config(app)
    return JSONResponse(content={"ok": True})


@router.put("/config/apeiria")
async def api_config_apeiria(data: dict) -> JSONResponse:
    _patch_config("apeiria", data)
    return JSONResponse(content={"ok": True})


def _patch_config(section: str, data: dict) -> None:
    import yaml

    p = Path("data/config.yaml")
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.exists() else {}
    if section in raw and isinstance(raw[section], dict) and isinstance(data, dict):
        raw[section] = {**raw[section], **data}
    else:
        raw[section] = data
    _write_yaml(raw)


@router.get("/store/plugins")
async def api_store_search(
    q: str = "", limit: int = 60, offset: int = 0, sort: str = ""
) -> JSONResponse:
    store = get_store()
    items = await store.search(q)
    page, total = paginate(items, offset, limit, sort)
    return JSONResponse(
        content={"results": [it.to_dict() for it in page], "total": total}
    )


@router.get("/store/plugins/{pkg_name}")
async def api_store_get(pkg_name: str) -> JSONResponse:
    store = get_store()
    item = await store.get(pkg_name)
    if item is None:
        raise HTTPException(status_code=404)
    return JSONResponse(content=item.to_dict())


@router.get("/store/adapters")
async def api_store_adapters_search(
    q: str = "", limit: int = 60, offset: int = 0, sort: str = ""
) -> JSONResponse:
    store = get_store()
    items = await store.search_adapters(q)
    page, total = paginate(items, offset, limit, sort)
    return JSONResponse(
        content={"results": [it.to_dict() for it in page], "total": total}
    )


@router.get("/store/sources")
async def api_store_sources() -> JSONResponse:
    return JSONResponse(content={"sources": ["nonebot"]})


@router.get("/status")
async def api_status() -> JSONResponse:
    return JSONResponse(content=get_status())


@router.get("/tasks/{task_id}/stream")
async def api_task_stream(request: Request, task_id: str) -> StreamingResponse:
    runner = get_task_runner()
    queue = await runner.subscribe(task_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if payload.get("type") in ("done", "error"):
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@router.post("/restart")
async def api_restart() -> JSONResponse:
    import asyncio as _asyncio
    import os
    import sys

    async def _delayed_restart() -> None:
        await _asyncio.sleep(0.5)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except OSError:
            pass

        if sys.platform == "win32":
            import subprocess

            subprocess.Popen(  # noqa: ASYNC220
                [sys.executable, *sys.argv],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
            )
            os._exit(0)
        else:
            os.execv(sys.executable, [sys.executable, *sys.argv])

    asyncio.ensure_future(  # noqa: RUF006
        _delayed_restart()
    )
    return JSONResponse(content={"ok": True})
