"""Bounded model invocation failure taxonomy."""

from __future__ import annotations

from typing import Literal

AIModelFailureReason = Literal[
    "configuration_error",
    "capability_unavailable",
    "model_timeout",
    "upstream_temporary_error",
    "upstream_permanent_error",
    "empty_response",
    "model_error",
]

_TEMPORARY_STATUS_CODES = {408, 409, 425, 429}
_CLIENT_ERROR_MIN_STATUS = 400
_SERVER_ERROR_MIN_STATUS = 500
_SERVER_ERROR_MAX_STATUS = 600
_TEMPORARY_MESSAGE_PARTS = (
    "temporar",
    "try again",
    "rate limit",
    "rate-limit",
    "overloaded",
    "unavailable",
    "connection reset",
    "connection refused",
)
_PERMANENT_MESSAGE_PARTS = (
    "unauthorized",
    "forbidden",
    "permission",
    "invalid request",
    "bad request",
    "not found",
    "quota exceeded",
)
_CONFIG_MESSAGE_PARTS = (
    "missing api_key",
    "missing api key",
    "missing api_base",
    "missing base url",
    "not configured",
    "configuration",
)
_CAPABILITY_MESSAGE_PARTS = (
    "unsupported",
    "not supported",
    "capability",
)


def classify_model_failure(  # noqa: C901, PLR0911
    exc: BaseException,
) -> AIModelFailureReason:
    """Classify one provider/model exception into a stable runtime reason."""

    class_name = type(exc).__name__.lower()
    message = str(exc).lower()
    status_code = _status_code(exc)

    if isinstance(exc, TimeoutError) or "timeout" in class_name or _timed_out(message):
        return "model_timeout"
    if "config" in class_name or any(part in message for part in _CONFIG_MESSAGE_PARTS):
        return "configuration_error"
    if "capability" in class_name or any(
        part in message for part in _CAPABILITY_MESSAGE_PARTS
    ):
        return "capability_unavailable"

    retryable = getattr(exc, "retryable", None)
    if retryable is True:
        return "upstream_temporary_error"
    if retryable is False:
        return "upstream_permanent_error"

    if status_code is not None:
        if (
            status_code in _TEMPORARY_STATUS_CODES
            or _SERVER_ERROR_MIN_STATUS <= status_code < _SERVER_ERROR_MAX_STATUS
        ):
            return "upstream_temporary_error"
        if _CLIENT_ERROR_MIN_STATUS <= status_code < _SERVER_ERROR_MIN_STATUS:
            return "upstream_permanent_error"

    if any(part in message for part in _TEMPORARY_MESSAGE_PARTS):
        return "upstream_temporary_error"
    if any(part in message for part in _PERMANENT_MESSAGE_PARTS):
        return "upstream_permanent_error"
    return "model_error"


def _timed_out(message: str) -> bool:
    return "timed out" in message or "timeout" in message


def _status_code(exc: BaseException) -> int | None:
    value = getattr(exc, "status_code", None)
    if value is None:
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "AIModelFailureReason",
    "classify_model_failure",
]
