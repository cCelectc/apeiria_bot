from __future__ import annotations

import ipaddress
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

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

_FAIL_THRESHOLD = 5
_BASE_DELAY = 2.0
_MAX_DELAY = 300.0
_MAX_BACKOFF_EXP = 10

_cache: dict[str, WebConfig] = {}
_login_failures: dict[str, tuple[int, float]] = {}


def _web() -> WebConfig:
    if "web" not in _cache:
        _cache["web"] = load_config(str(CONFIG_PATH)).apeiria.web
    return _cache["web"]


def _invalidate() -> None:
    _cache.pop("web", None)


def _persist_web(fields: dict[str, object]) -> None:
    raw: dict = {}
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    apeiria = raw.get("apeiria")
    if not isinstance(apeiria, dict):
        apeiria = {}
        raw["apeiria"] = apeiria
    web = apeiria.get("web")
    if not isinstance(web, dict):
        web = {}
        apeiria["web"] = web
    web.update(fields)
    CONFIG_PATH.write_text(
        yaml.dump(raw, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    _invalidate()


def ensure_credentials() -> None:
    """Generate admin password and JWT secret on first run, persist, log once."""
    web = _web()
    updates: dict[str, object] = {}
    plaintext: str | None = None
    if not web.password_hash:
        plaintext = generate_dashboard_password()
        updates["password_hash"] = hash_dashboard_password(plaintext)
    if not web.jwt_secret:
        updates["jwt_secret"] = secrets.token_urlsafe(_JWT_SECRET_BYTES)
    if updates:
        _persist_web(updates)
    if plaintext is not None:
        logger.warning(
            "WebUI 初始管理员凭据已生成（仅显示一次）：用户名={} 密码={}",
            web.username,
            plaintext,
        )


def reset_password(new_password: str | None = None) -> str:
    """Reset admin password (generate if not given), persist, return plaintext."""
    plaintext = new_password or generate_dashboard_password()
    _persist_web({"password_hash": hash_dashboard_password(plaintext)})
    return plaintext


def _issue_token(username: str) -> str:
    web = _web()
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(days=web.token_expire_days),
    }
    return jwt.encode(payload, web.jwt_secret, algorithm=_JWT_ALGORITHM)


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
    web = _web()
    try:
        payload = jwt.decode(token, web.jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Invalid token")
    return sub


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
    web = _web()
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
    web = _web()
    ok = data.username == web.username and verify_dashboard_password(
        web.password_hash, data.password
    )
    if not ok:
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _reset_failures(key)
    token = _issue_token(web.username)
    return JSONResponse(content={"token": token, "username": web.username})


@auth_router.post("/change-password", dependencies=[Depends(verify_token)])
async def change_password(data: ChangePasswordRequest) -> JSONResponse:
    web = _web()
    if not verify_dashboard_password(web.password_hash, data.old_password):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    try:
        validate_dashboard_password(data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_web({"password_hash": hash_dashboard_password(data.new_password)})
    return JSONResponse(content={"ok": True})
