from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

try:  # pragma: no cover - optional dependency
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except Exception:  # pragma: no cover - keep local dev working without extra deps
    PasswordHasher = None
    VerifyMismatchError = Exception

_PASSWORD_PEPPER = "macro-tracker"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _argon_hasher() -> PasswordHasher | None:
    if PasswordHasher is None:  # pragma: no cover - depends on optional package
        return None
    return PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(password: str) -> str:
    hasher = _argon_hasher()
    if hasher is not None:  # pragma: no branch - simple guard
        return hasher.hash(password)

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return "scrypt$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False

    if password_hash.startswith("$argon2"):
        hasher = _argon_hasher()
        if hasher is None:
            return False
        try:
            return bool(hasher.verify(password_hash, password))
        except VerifyMismatchError:
            return False

    if not password_hash.startswith("scrypt$"):
        return False

    try:
        _, encoded_salt, encoded_digest = password_hash.split("$", 2)
    except ValueError:
        return False
    salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
    expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return secrets.compare_digest(expected, actual)


def create_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(f"{_PASSWORD_PEPPER}:{token}".encode("utf-8")).hexdigest()


def session_expires_at(hours: int) -> datetime:
    return _now() + timedelta(hours=hours)


@dataclass(slots=True)
class SessionTokenBundle:
    token: str
    token_hash: str
    expires_at: datetime


def build_session_bundle(hours: int) -> SessionTokenBundle:
    token = create_session_token()
    return SessionTokenBundle(
        token=token,
        token_hash=hash_session_token(token),
        expires_at=session_expires_at(hours),
    )
