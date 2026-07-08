from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from apeiria.config.contract import resolve_config_namespace_contract
from apeiria.config.loader import load_config, update_runtime_config
from apeiria.config.models import ApeiriaConfig
from apeiria.config.reflector import reflect_model
from apeiria.plugin.adapter_manager import (
    set_adapter_state,
)
from apeiria.plugin.adapter_scanner import scan_adapters
from apeiria.plugin.manager import set_plugin_state
from apeiria.plugin.scanner import scan_plugins
from apeiria.web.auth import verify_token
from apeiria.web.plugin_metadata import merge_plugin_metadata
from apeiria.web.store import get_status, get_store, paginate
from apeiria.web.tasks import get_task_runner

if TYPE_CHECKING:
    from apeiria.db.models.access import AccessRule

router = APIRouter(prefix="/api", dependencies=[Depends(verify_token)])


def _write_yaml(raw: dict) -> None:
    import yaml

    p = Path("data/config.yaml")
    p.write_text(
        yaml.dump(raw, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def _scanned_name_to_module(name: str) -> str | None:
    from apeiria.plugin.scanner import manifest_module_candidate, scan_plugins

    for manifest in scan_plugins():
        if manifest.name == name:
            return manifest_module_candidate(manifest)
    return None


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
                "installed_version": None,
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
        module = _scanned_name_to_module(name)
        if module is not None and module != name:
            contract = resolve_config_namespace_contract(module)

    if contract.source == "none" and not contract.fields:
        raise HTTPException(status_code=404, detail="No config for this plugin")

    app = load_config("data/config.yaml")
    values = app.plugins.get(name, {})
    return JSONResponse(content={**contract.to_dict(), "values": values})


@router.get("/adapters/list")
async def api_adapters_list() -> JSONResponse:
    from apeiria.plugin.adapter_manager import _read_adapters_yaml
    from apeiria.plugin.scanner import read_installed_version

    pkgs = _read_adapters_yaml().get("packages") or {}
    items = [
        {
            "name": a.name,
            "source": a.source,
            "enabled": a.enabled,
            "module_name": a.module_name,
            "installed_version": read_installed_version(pkgs[a.name])
            if a.source == "pypi" and a.name in pkgs
            else None,
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
    if "driver" in data:
        current = load_config("data/config.yaml").nonebot.driver
        if data["driver"] != current:
            raise HTTPException(
                status_code=422,
                detail="Cannot modify protected config: driver",
            )
        data.pop("driver")
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
    from apeiria.utils.restart import graceful_restart

    async def _delayed_restart() -> None:
        await asyncio.sleep(0.5)
        await graceful_restart()

    asyncio.ensure_future(_delayed_restart())  # noqa: RUF006
    return JSONResponse(content={"ok": True})


@router.get("/plugins/names")
async def api_plugins_names() -> JSONResponse:
    import nonebot

    names: list[str] = []
    seen: set[str] = set()
    for m in scan_plugins():
        if m.name not in seen:
            names.append(m.name)
            seen.add(m.name)
    for plugin in nonebot.get_loaded_plugins():
        if plugin.name not in seen:
            names.append(plugin.name)
            seen.add(plugin.name)
    return JSONResponse(content={"names": sorted(names)})


access_router = APIRouter(prefix="/api/access", dependencies=[Depends(verify_token)])


def _rule_to_dict(rule: "AccessRule") -> dict:
    return {
        "id": rule.id,
        "subject_type": rule.subject_type,
        "subject_id": rule.subject_id,
        "plugin_name": rule.plugin_name,
        "action": rule.action,
        "priority": rule.priority,
    }


async def _reload_access() -> None:
    from apeiria.bootstrap.steps import get_access_control

    await get_access_control().load_snapshot()


@access_router.get("/rules")
async def api_access_rules_list() -> JSONResponse:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.access import AccessRule

    db = get_db()
    async with db.gate.read() as session:
        result = await session.execute(
            select(AccessRule).order_by(AccessRule.priority.desc())
        )
        rules = result.scalars().all()
    return JSONResponse(content={"rules": [_rule_to_dict(r) for r in rules]})


@access_router.post("/rules")
async def api_access_rules_create(data: dict) -> JSONResponse:
    from sqlalchemy import func

    from apeiria.db import get_db
    from apeiria.db.models.access import AccessRule

    subject_type = data.get("subject_type", "")
    subject_id = data.get("subject_id", "")
    action = data.get("action", "")

    if subject_type not in ("user", "group"):
        raise HTTPException(
            status_code=400, detail="subject_type must be user or group"
        )
    if not subject_id:
        raise HTTPException(status_code=400, detail="subject_id required")
    if action not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="action must be allow or deny")

    db = get_db()
    priority = data.get("priority")
    if priority is None:
        async with db.gate.read() as session:
            result = await session.execute(func.min(AccessRule.priority))
            min_val = result.scalar_one_or_none()
            priority = (min_val - 1) if min_val is not None else 0

    plugin_name = data.get("plugin_name") or None
    async with db.gate.write() as session:
        rule = AccessRule(
            subject_type=subject_type,
            subject_id=subject_id,
            plugin_name=plugin_name,
            action=action,
            priority=priority,
        )
        session.add(rule)
        await session.commit()
    await _reload_access()
    return JSONResponse(
        content={"ok": True, "rule": _rule_to_dict(rule)}, status_code=201
    )


@access_router.put("/rules/{rule_id}")
async def api_access_rules_update(rule_id: int, data: dict) -> JSONResponse:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.access import AccessRule

    db = get_db()
    async with db.gate.write() as session:
        result = await session.execute(
            select(AccessRule).where(AccessRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")

        for field in (
            "subject_type",
            "subject_id",
            "plugin_name",
            "action",
            "priority",
        ):
            if field in data:
                value = data[field]
                if field == "subject_type" and value not in ("user", "group"):
                    raise HTTPException(
                        status_code=400, detail="subject_type must be user or group"
                    )
                if field == "action" and value not in ("allow", "deny"):
                    raise HTTPException(
                        status_code=400, detail="action must be allow or deny"
                    )
                setattr(rule, field, data[field])
        await session.commit()
    await _reload_access()
    return JSONResponse(content={"ok": True, "rule": _rule_to_dict(rule)})


@access_router.delete("/rules/{rule_id}")
async def api_access_rules_delete(rule_id: int) -> JSONResponse:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.access import AccessRule

    db = get_db()
    async with db.gate.write() as session:
        result = await session.execute(
            select(AccessRule).where(AccessRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        await session.delete(rule)
        await session.commit()
    await _reload_access()
    return JSONResponse(content={"ok": True})


@access_router.post("/rules/reorder")
async def api_access_rules_reorder(data: dict) -> JSONResponse:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.access import AccessRule

    ids = data.get("ids", [])
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="ids must be a non-empty list")

    total = len(ids)
    db = get_db()
    async with db.gate.write() as session:
        for idx, rule_id in enumerate(ids):
            result = await session.execute(
                select(AccessRule).where(AccessRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()
            if rule is not None:
                rule.priority = total - idx
        await session.commit()
    await _reload_access()
    return JSONResponse(content={"ok": True})


@access_router.get("/rules/preview")
async def api_access_rules_preview(
    subject_type: Annotated[str, Query()],
    subject_id: Annotated[str, Query()],
    plugin_name: Annotated[str, Query()] = "",
) -> JSONResponse:
    if subject_type == "user":
        user_id, group_id = subject_id, None
    elif subject_type == "group":
        user_id, group_id = "", subject_id
    else:
        raise HTTPException(status_code=400, detail="Invalid subject_type")

    from apeiria.bootstrap.steps import get_access_control

    ac = get_access_control()
    result = ac.evaluate_with_detail(user_id, group_id, plugin_name)
    return JSONResponse(content=result)


@access_router.get("/subjects/search")
async def api_access_subjects_search(
    q: Annotated[str, Query()] = "",
    subject_type_q: Annotated[str, Query(alias="type")] = "user",
) -> JSONResponse:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.conversation import Session

    db = get_db()
    async with db.gate.read() as session:
        if subject_type_q == "user":
            result = await session.execute(
                select(Session.scene_id)
                .where(
                    Session.scene_type != "group",
                    Session.scene_id.like(f"%{q}%"),
                )
                .distinct()
                .limit(20)
            )
        elif subject_type_q == "group":
            result = await session.execute(
                select(Session.scene_id)
                .where(
                    Session.scene_type == "group",
                    Session.scene_id.like(f"%{q}%"),
                )
                .distinct()
                .limit(20)
            )
        else:
            raise HTTPException(status_code=400, detail="type must be user or group")

        subjects = [{"id": row[0], "type": subject_type_q} for row in result.all()]
    return JSONResponse(content={"subjects": subjects})
