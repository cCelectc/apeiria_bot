from __future__ import annotations

import asyncio
import ipaddress
import secrets
import time
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jwt
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from nonebot.log import logger
from pydantic import BaseModel

from apeiria.config.loader import load_config
from apeiria.web.auth_password import (
    generate_dashboard_password,
    hash_dashboard_password,
    validate_dashboard_password,
    verify_dashboard_password,
)

if TYPE_CHECKING:
    from apeiria.config.models import WebConfig

CONFIG_PATH = Path("data/config.yaml")
_JWT_ALGORITHM = "HS256"
_JWT_SECRET_BYTES = 48
_SETTING_PASSWORD_HASH = "password_hash"
_SETTING_JWT_SECRET = "jwt_secret"

_FAIL_THRESHOLD = 5
_BASE_DELAY = 2.0
_MAX_DELAY = 300.0
_MAX_BACKOFF_EXP = 10

_web_cache: list[WebConfig | None] = [None]  # type: ignore[valid-type]
_login_failures: dict[str, tuple[int, float]] = {}


def _web_config() -> WebConfig:  # type: ignore[valid-type]
    if _web_cache[0] is None:
        _web_cache[0] = load_config(str(CONFIG_PATH)).apeiria.web
    return _web_cache[0]


def _clear_web_cache() -> None:
    _web_cache[0] = None


async def _get_setting(key: str) -> str | None:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.setting import ApeiriaSetting

    db = get_db()
    async with db.gate.read() as session:
        result = await session.execute(
            select(ApeiriaSetting.value).where(ApeiriaSetting.key == key)
        )
        return result.scalar_one_or_none()


async def _set_setting(key: str, value: str) -> None:
    from sqlalchemy import select

    from apeiria.db import get_db
    from apeiria.db.models.setting import ApeiriaSetting

    db = get_db()
    async with db.gate.write() as session:
        result = await session.execute(
            select(ApeiriaSetting).where(ApeiriaSetting.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.value = value
        else:
            session.add(ApeiriaSetting(key=key, value=value))


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _migrate_from_yaml() -> tuple[str | None, str | None]:
    if not CONFIG_PATH.exists():
        return None, None
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    web_section = raw.get("apeiria", {}).get("web", {})
    if not isinstance(web_section, dict):
        return None, None

    password_hash = web_section.get("password_hash", "")
    jwt_secret = web_section.get("jwt_secret", "")

    changed = False
    if "jwt_secret" in web_section:
        del web_section["jwt_secret"]
        changed = True
    if "password_hash" in web_section:
        del web_section["password_hash"]
        changed = True

    if changed:
        CONFIG_PATH.write_text(
            yaml.dump(raw, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        _clear_web_cache()
        logger.info("Migrated password_hash and jwt_secret from config.yaml to DB")

    pw = password_hash if isinstance(password_hash, str) and password_hash else None
    jw = jwt_secret if isinstance(jwt_secret, str) and jwt_secret else None
    return pw, jw


def ensure_credentials() -> None:
    web = _web_config()
    legacy_hash, legacy_jwt = _migrate_from_yaml()

    plaintext: str | None = None

    existing_hash = _run_async(_get_setting(_SETTING_PASSWORD_HASH))
    if not existing_hash and legacy_hash:
        _run_async(_set_setting(_SETTING_PASSWORD_HASH, legacy_hash))
    elif not existing_hash:
        plaintext = generate_dashboard_password()
        _run_async(
            _set_setting(_SETTING_PASSWORD_HASH, hash_dashboard_password(plaintext))
        )

    existing_jwt = _run_async(_get_setting(_SETTING_JWT_SECRET))
    if not existing_jwt and legacy_jwt:
        _run_async(_set_setting(_SETTING_JWT_SECRET, legacy_jwt))
    elif not existing_jwt:
        _run_async(
            _set_setting(_SETTING_JWT_SECRET, secrets.token_urlsafe(_JWT_SECRET_BYTES))
        )

    if plaintext is not None:
        logger.warning(
            "WebUI 初始管理员凭据已生成（仅显示一次）：用户名={} 密码={}",
            web.username,
            plaintext,
        )


def reset_password(new_password: str | None = None) -> str:
    plaintext = new_password or generate_dashboard_password()
    _run_async(_set_setting(_SETTING_PASSWORD_HASH, hash_dashboard_password(plaintext)))
    return plaintext


async def _require_password_hash() -> str:
    ph = await _get_setting(_SETTING_PASSWORD_HASH)
    if not ph:
        raise HTTPException(status_code=500, detail="Credentials not initialized")
    return ph


async def _require_jwt_secret() -> str:
    js = await _get_setting(_SETTING_JWT_SECRET)
    if not js:
        raise HTTPException(status_code=500, detail="Credentials not initialized")
    return js


def _issue_token(username: str, jwt_secret: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(days=_web_config().token_expire_days),
    }
    return jwt.encode(payload, jwt_secret, algorithm=_JWT_ALGORITHM)


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip() or None
    cookie = request.cookies.get("access_token")
    if cookie:
        return cookie
    return request.query_params.get("token") or None


async def verify_token(request: Request) -> str:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    jwt_secret = await _require_jwt_secret()
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Invalid token")
    return sub


async def decode_token(token: str) -> str | None:
    """解码 JWT 并返回 subject（用户名），无效/过期/未初始化时返回 None。

    用于 HTTP 请求上下文之外的鉴权（如 WebSocket 握手）。
    """
    if not token:
        return None
    try:
        jwt_secret = await _require_jwt_secret()
    except HTTPException:
        return None
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def _is_trusted(peer: str, proxies: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for entry in proxies:
        try:
            if addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def _resolve_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    web = _web_config()
    if not web.real_ip_header or not web.trusted_proxies:
        return peer
    if not _is_trusted(peer, web.trusted_proxies):
        return peer
    forwarded = request.headers.get(web.real_ip_header, "")
    if not forwarded:
        return peer
    return forwarded.split(",")[0].strip() or peer


def _retry_after(key: str) -> float:
    count, last = _login_failures.get(key, (0, 0.0))
    if count < _FAIL_THRESHOLD:
        return 0.0
    exponent = min(count - _FAIL_THRESHOLD, _MAX_BACKOFF_EXP)
    required = min(_BASE_DELAY * (2**exponent), _MAX_DELAY)
    elapsed = time.monotonic() - last
    return max(0.0, required - elapsed)


def _record_failure(key: str) -> None:
    count, _ = _login_failures.get(key, (0, 0.0))
    _login_failures[key] = (count + 1, time.monotonic())


def _reset_failures(key: str) -> None:
    _login_failures.pop(key, None)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/login")
async def login(data: LoginRequest, request: Request) -> JSONResponse:
    key = _resolve_client_ip(request)
    wait = _retry_after(key)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts",
            headers={"Retry-After": str(int(wait) + 1)},
        )
    web = _web_config()
    password_hash = await _require_password_hash()
    ok = data.username == web.username and verify_dashboard_password(
        password_hash, data.password
    )
    if not ok:
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _reset_failures(key)
    jwt_secret = await _require_jwt_secret()
    token = _issue_token(web.username, jwt_secret)
    return JSONResponse(content={"token": token, "username": web.username})


@auth_router.post("/change-password", dependencies=[Depends(verify_token)])
async def change_password(data: ChangePasswordRequest) -> JSONResponse:
    password_hash = await _require_password_hash()
    if not verify_dashboard_password(password_hash, data.old_password):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    try:
        validate_dashboard_password(data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _set_setting(
        _SETTING_PASSWORD_HASH, hash_dashboard_password(data.new_password)
    )
    return JSONResponse(content={"ok": True})
