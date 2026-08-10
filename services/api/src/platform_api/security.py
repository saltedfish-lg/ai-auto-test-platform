"""Frozen P1 Argon2id, JWT, opaque Refresh token and ULID primitives."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from platform_api.errors import PlatformError

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
COMMON_PASSWORD_DENYLIST_VERSION = "v1"


def _load_common_passwords() -> frozenset[str]:
    resource = files("platform_api").joinpath(
        "data", f"common-passwords-{COMMON_PASSWORD_DENYLIST_VERSION}.txt"
    )
    entries: list[str] = []
    for raw_line in resource.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        if raw_line != raw_line.strip() or raw_line != raw_line.casefold():
            raise RuntimeError("common-password denylist must contain normalized entries")
        entries.append(raw_line)
    if len(entries) < 25 or len(entries) != len(set(entries)):
        raise RuntimeError("common-password denylist is incomplete or contains duplicates")
    return frozenset(entries)


_COMMON_PASSWORDS = _load_common_passwords()


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_ulid() -> str:
    value = ((time.time_ns() // 1_000_000) << 80) | int.from_bytes(secrets.token_bytes(10))
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_refresh_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def refresh_token_hash(token: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("invalid refresh token format")
    try:
        decoded = base64.b64decode(token + "=", altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise ValueError("invalid refresh token format") from error
    if len(decoded) != 32:
        raise ValueError("invalid refresh token format")
    return hashlib.sha256(token.encode("ascii")).digest()


def client_context_hash(value: str | None) -> bytes | None:
    return hashlib.sha256(value.encode("utf-8")).digest() if value else None


class PasswordPolicyError(ValueError):
    pass


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=1,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def validate(self, password: str, username: str) -> None:
        if not 12 <= len(password) <= 128:
            raise PasswordPolicyError("password length must be between 12 and 128")
        if password != password.strip() or not password.strip():
            raise PasswordPolicyError("password must not have leading or trailing whitespace")
        if not any(char.isalpha() for char in password) or not any(
            char.isdigit() for char in password
        ):
            raise PasswordPolicyError("password must contain a letter and a digit")
        if password.casefold() == username.casefold():
            raise PasswordPolicyError("password must differ from username")
        if password.casefold() in _COMMON_PASSWORDS:
            raise PasswordPolicyError("password is present in the common-password denylist")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, encoded_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except (InvalidHashError, VerifyMismatchError):
            return False

    def verify_dummy(self, password: str) -> None:
        self.verify(self._dummy_hash, password)

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            parameters = extract_parameters(encoded_hash)
        except InvalidHashError:
            return False
        return (
            parameters.type is not Type.ID
            or parameters.version < 19
            or parameters.memory_cost < 65536
            or parameters.time_cost < 3
            or parameters.parallelism < 1
            or parameters.hash_len < 32
            or parameters.salt_len < 16
        )


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: str
    session_id: str
    credential_version: int


class JwtService:
    issuer = "ai-auto-test-platform"
    audience = "ai-auto-test-platform-api"
    ttl_seconds = 900
    clock_skew_seconds = 60

    def __init__(self, private_key_file: Path | None, public_key_file: Path | None, kid: str):
        if private_key_file is None or public_key_file is None:
            raise RuntimeError("RS256 key files are required for authentication")
        self._private_key = private_key_file.read_bytes()
        self._public_key = public_key_file.read_bytes()
        self._kid = kid

    def issue(self, claims: AccessClaims, *, now: datetime | None = None) -> str:
        issued = (now or datetime.now(UTC)).astimezone(UTC)
        payload: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": claims.user_id,
            "iat": issued,
            "exp": issued + timedelta(seconds=self.ttl_seconds),
            "jti": new_ulid(),
            "token_use": "access",
            "session_id": claims.session_id,
            "credential_version": claims.credential_version,
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._kid},
        )

    def decode(self, token: str) -> AccessClaims:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("kid") != self._kid or header.get("alg") != "RS256":
                raise PlatformError(
                    title="Invalid access token",
                    detail="The access token is invalid.",
                    status=401,
                    code="AUTH_TOKEN_INVALID",
                )
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.clock_skew_seconds,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "iat",
                        "exp",
                        "jti",
                        "token_use",
                        "session_id",
                        "credential_version",
                    ]
                },
            )
            if payload["token_use"] != "access":
                raise jwt.InvalidTokenError
            user_id = str(payload["sub"])
            session_id = str(payload["session_id"])
            credential_version = int(payload["credential_version"])
            if len(user_id) != 26 or len(session_id) != 26 or credential_version < 1:
                raise jwt.InvalidTokenError
            return AccessClaims(user_id, session_id, credential_version)
        except jwt.ExpiredSignatureError as error:
            raise PlatformError(
                title="Expired access token",
                detail="The access token has expired.",
                status=401,
                code="AUTH_TOKEN_EXPIRED",
            ) from error
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise PlatformError(
                title="Invalid access token",
                detail="The access token is invalid.",
                status=401,
                code="AUTH_TOKEN_INVALID",
            ) from error
