from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string

_SCRYPT_PREFIX = "scrypt"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_SCRYPT_SALT_BYTES = 16
_HASH_PARTS = 6

_PASSWORD_MIN_LENGTH = 8
_GENERATED_PASSWORD_LENGTH = 24


def _scrypt(raw_password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        raw_password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=_SCRYPT_MAXMEM,
        dklen=_SCRYPT_DKLEN,
    )


def hash_dashboard_password(raw_password: str) -> str:
    """Return a salted scrypt hash as ``scrypt$n$r$p$salt$digest``."""
    if not raw_password:
        msg = "Password cannot be empty"
        raise ValueError(msg)
    salt = secrets.token_bytes(_SCRYPT_SALT_BYTES)
    digest = _scrypt(raw_password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return (
        f"{_SCRYPT_PREFIX}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_dashboard_password(stored_hash: str, candidate_password: str) -> bool:
    """Verify a candidate password against a stored scrypt hash."""
    if not stored_hash or not candidate_password:
        return False
    parts = stored_hash.split("$")
    if len(parts) != _HASH_PARTS or parts[0] != _SCRYPT_PREFIX:
        return False
    try:
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        expected = bytes.fromhex(parts[5])
    except ValueError:
        return False
    candidate = _scrypt(candidate_password, salt, n, r, p)
    return hmac.compare_digest(candidate, expected)


def generate_dashboard_password() -> str:
    """Generate a strong password satisfying the complexity policy."""
    alphabet = string.ascii_letters + string.digits
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        *(secrets.choice(alphabet) for _ in range(_GENERATED_PASSWORD_LENGTH - 3)),
    ]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def validate_dashboard_password(raw_password: str) -> None:
    """Raise ``ValueError`` if the password fails the complexity policy."""
    if not raw_password:
        msg = "Password cannot be empty"
        raise ValueError(msg)
    if len(raw_password) < _PASSWORD_MIN_LENGTH:
        msg = f"Password must be at least {_PASSWORD_MIN_LENGTH} characters long"
        raise ValueError(msg)
    if not re.search(r"[A-Z]", raw_password):
        msg = "Password must include at least one uppercase letter"
        raise ValueError(msg)
    if not re.search(r"[a-z]", raw_password):
        msg = "Password must include at least one lowercase letter"
        raise ValueError(msg)
    if not re.search(r"\d", raw_password):
        msg = "Password must include at least one digit"
        raise ValueError(msg)
