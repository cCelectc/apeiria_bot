from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from apeiria.config.loader import load_config, update_runtime_config
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
    ok = install_plugin(name, pkg)
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
    if contract is None:
        raise HTTPException(status_code=404)
    fields = [
        {
            "key": c.key,
            "label": c.label or c.key,
            "help": c.help,
            "type": str(c.type) if c.type else "str",
            "default": c.default,
            "order": c.order,
            "secret": c.secret,
            "choices": c.choices,
        }
        for c in contract.configs
    ]
    return JSONResponse(content={"fields": fields})


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
    raw[section] = data
    _write_yaml(raw)


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
