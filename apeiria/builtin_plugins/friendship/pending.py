from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

from .models import PendingRequest

_STORE_FILE: Path | None = None
_STORE_LOCK = asyncio.Lock()
_TTL = timedelta(days=7)


def _store_path() -> Path:
    global _STORE_FILE  # noqa: PLW0603
    if _STORE_FILE is None:
        _STORE_FILE = get_plugin_data_file("pending_requests.yaml")
    return _STORE_FILE


def _generate_id(pending_list: list[PendingRequest]) -> str:
    kind_prefixes = {"friend": "f", "group_add": "g", "group_invite": "g"}
    existing_nums: dict[str, int] = {}
    for p in pending_list:
        if not p.id:
            continue
        prefix = p.id[0]
        try:
            n = int(p.id[1:])
        except (ValueError, IndexError):
            continue
        existing_nums[prefix] = max(existing_nums.get(prefix, 0), n)
    prefix = "f"
    for p in pending_list:
        if p.status == "pending":
            prefix = kind_prefixes.get(p.kind, "f")
            break
    n = existing_nums.get(prefix, 0) + 1
    return f"{prefix}{n}"


def _load() -> list[dict]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:  # noqa: BLE001
        logger.warning("failed to load pending requests, resetting")
    return []


def _save(requests: list[PendingRequest]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "id": r.id,
            "provider_key": r.provider_key,
            "bot_self_id": r.bot_self_id,
            "scope": r.scope,
            "raw_flag": r.raw_flag,
            "kind": r.kind,
            "requester_id": r.requester_id,
            "requester_name": r.requester_name,
            "comment": r.comment,
            "sub_type": r.sub_type,
            "group_id": r.group_id,
            "group_name": r.group_name,
            "created_at": r.created_at,
            "status": r.status,
            "notified": r.notified,
        }
        for r in requests
    ]
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def _data_to_pending(d: dict) -> PendingRequest:
    return PendingRequest(
        id=d.get("id", ""),
        provider_key=d.get("provider_key", ""),
        bot_self_id=d.get("bot_self_id", ""),
        scope=d.get("scope", ""),
        raw_flag=d.get("raw_flag", ""),
        kind=d.get("kind", "friend"),
        requester_id=d.get("requester_id", ""),
        requester_name=d.get("requester_name", ""),
        comment=d.get("comment", ""),
        sub_type=d.get("sub_type"),
        group_id=d.get("group_id"),
        group_name=d.get("group_name"),
        created_at=d.get("created_at", ""),
        status=d.get("status", "pending"),
        notified=d.get("notified", {}),
    )


async def load_all() -> list[PendingRequest]:
    async with _STORE_LOCK:
        return [_data_to_pending(d) for d in _load()]


async def add_pending(pending: PendingRequest) -> None:
    async with _STORE_LOCK:
        items = [_data_to_pending(d) for d in _load()]
        pending.id = _generate_id([*items, pending])
        items.append(pending)
        _cleanup(items)
        _save(items)


async def remove_pending(request_id: str) -> bool:
    async with _STORE_LOCK:
        items = [_data_to_pending(d) for d in _load()]
        removed = [r for r in items if r.id == request_id]
        items = [r for r in items if r.id != request_id]
        if removed:
            _save(items)
            return True
    return False


async def get_pending(request_id: str) -> PendingRequest | None:
    async with _STORE_LOCK:
        items = [_data_to_pending(d) for d in _load()]
        for r in items:
            if r.id == request_id:
                return r
    return None


async def update_notified(request_id: str, superuser_id: str, msg_id: str) -> None:
    async with _STORE_LOCK:
        items = [_data_to_pending(d) for d in _load()]
        for r in items:
            if r.id == request_id:
                r.notified[superuser_id] = msg_id
                break
        _save(items)


async def find_by_notified_msg(msg_id: str) -> PendingRequest | None:
    async with _STORE_LOCK:
        items = [_data_to_pending(d) for d in _load()]
        for r in items:
            if msg_id in r.notified.values():
                return r
    return None


def _cleanup(items: list[PendingRequest]) -> None:
    cutoff = datetime.now(UTC) - _TTL
    items[:] = [
        r
        for r in items
        if r.status == "pending" and datetime.fromisoformat(r.created_at) > cutoff
    ]
