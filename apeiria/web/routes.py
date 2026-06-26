from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from apeiria.config.loader import load_config, update_runtime_config
from apeiria.plugin.adapter_manager import (
    install_adapter,
    set_adapter_state,
    uninstall_adapter,
)
from apeiria.plugin.adapter_scanner import scan_adapters
from apeiria.plugin.manager import install_plugin, set_plugin_state, uninstall_plugin
from apeiria.plugin.metadata.resolver import resolve_config_namespace_contract
from apeiria.plugin.scanner import scan_plugins
from apeiria.web.store import get_status, get_store

router = APIRouter(prefix="/api")


def _write_yaml(raw: dict) -> None:
    import yaml

    p = Path("data/config.yaml")
    p.write_text(
        yaml.dump(raw, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


@router.get("/plugins/list")
async def api_plugins_list() -> JSONResponse:
    items = [
        {
            "name": p.name,
            "source": p.source,
            "enabled": p.enabled,
            "path_or_module": p.path_or_module,
        }
        for p in scan_plugins()
    ]
    return JSONResponse(content={"plugins": items})


@router.post("/plugins/install")
async def api_plugins_install(data: dict) -> JSONResponse:
    name = data.get("name", "")
    pkg = data.get("pkg", "")
    if not name or not pkg:
        raise HTTPException(status_code=400, detail="name and pkg required")
    ok = await asyncio.to_thread(install_plugin, name, pkg)
    return JSONResponse(content={"ok": ok})


@router.post("/plugins/uninstall")
async def api_plugins_uninstall(data: dict) -> JSONResponse:
    name = data.get("name", "")
    keep_config = data.get("keep_config", False)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    ok = uninstall_plugin(name, keep_config=keep_config)
    return JSONResponse(content={"ok": ok})


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
    if not contract.has_config_model and not contract.configs:
        raise HTTPException(status_code=404)
    fields = [
        {
            "key": c.key,
            "label": c.label or c.key,
            "help": c.help,
            "type": _type_name(c.type),
            "default": c.default,
            "order": c.order,
            "secret": c.secret,
            "choices": c.choices,
        }
        for c in contract.configs
    ]
    return JSONResponse(content={"fields": fields})


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
    ok = await asyncio.to_thread(install_adapter, name, pkg, module_name)
    return JSONResponse(content={"ok": ok})


@router.post("/adapters/uninstall")
async def api_adapters_uninstall(data: dict) -> JSONResponse:
    name = data.get("name", "")
    keep_config = data.get("keep_config", False)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    ok = uninstall_adapter(name, keep_config=keep_config)
    return JSONResponse(content={"ok": ok})


@router.post("/adapters/state")
async def api_adapters_state(data: dict) -> JSONResponse:
    name = data.get("name", "")
    enabled = data.get("enabled", True)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    ok = set_adapter_state(name, enabled)
    return JSONResponse(content={"ok": ok})


@router.get("/config")
async def api_config_get() -> JSONResponse:
    app = load_config("data/config.yaml")
    return JSONResponse(content=app.model_dump())


@router.put("/config/nonebot")
async def api_config_nonebot(data: dict) -> JSONResponse:
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


def _type_name(t: object) -> str:
    mapping = {
        str: "str",
        int: "int",
        float: "float",
        bool: "bool",
        list: "list",
        dict: "dict",
        type(None): "none",
    }
    if t in mapping:
        return mapping[t]
    name = getattr(t, "__name__", None)
    return str(name) if isinstance(name, str) else str(t)


@router.get("/store/plugins")
async def api_store_search(q: str = "") -> JSONResponse:
    store = get_store()
    items = await store.search(q)
    return JSONResponse(content={"results": [it.to_dict() for it in items]})


@router.get("/store/plugins/{pkg_name}")
async def api_store_get(pkg_name: str) -> JSONResponse:
    store = get_store()
    item = await store.get(pkg_name)
    if item is None:
        raise HTTPException(status_code=404)
    return JSONResponse(content=item.to_dict())


@router.get("/store/adapters")
async def api_store_adapters_search(q: str = "") -> JSONResponse:
    store = get_store()
    items = await store.search_adapters(q)
    return JSONResponse(content={"results": [it.to_dict() for it in items]})


@router.get("/store/sources")
async def api_store_sources() -> JSONResponse:
    return JSONResponse(content={"sources": ["nonebot"]})


@router.get("/status")
async def api_status() -> JSONResponse:
    return JSONResponse(content=get_status())


FRONTEND_DIR = Path("web/dist")


@router.get("/{full_path:path}")
async def serve_frontend(full_path: str) -> FileResponse:
    if not FRONTEND_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    file_path = FRONTEND_DIR / full_path
    if not file_path.exists() or not file_path.is_file():
        file_path = FRONTEND_DIR / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(file_path))
