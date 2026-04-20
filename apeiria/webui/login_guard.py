from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_FAILURE_WINDOW = timedelta(minutes=10)
_LOCK_DURATION = timedelta(minutes=15)
_MAX_FAILURES = 5


@dataclass
class LoginThrottleState:
    failures: deque[datetime]
    locked_until: datetime | None = None


_states: dict[str, LoginThrottleState] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_key(username: str, client_ip: str) -> str:
    return f"{username.strip().lower()}|{client_ip.strip()}"


def _prune(state: LoginThrottleState, *, now: datetime) -> None:
    threshold = now - _FAILURE_WINDOW
    while state.failures and state.failures[0] < threshold:
        state.failures.popleft()
    if state.locked_until is not None and state.locked_until <= now:
        state.locked_until = None


def is_login_allowed(username: str, client_ip: str) -> bool:
    key = _build_key(username, client_ip)
    state = _states.get(key)
    if state is None:
        return True
    now = _now()
    _prune(state, now=now)
    return state.locked_until is None


def record_login_failure(username: str, client_ip: str) -> None:
    key = _build_key(username, client_ip)
    state = _states.setdefault(key, LoginThrottleState(failures=deque()))
    now = _now()
    _prune(state, now=now)
    state.failures.append(now)
    if len(state.failures) >= _MAX_FAILURES:
        state.locked_until = now + _LOCK_DURATION


def record_login_success(username: str, client_ip: str) -> None:
    key = _build_key(username, client_ip)
    if key in _states:
        _states.pop(key, None)
