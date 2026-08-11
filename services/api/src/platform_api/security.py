"""Frozen P1 Argon2id, JWT, opaque Refresh token and ULID primitives."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

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


@dataclass(frozen=True, slots=True)
class JwtVerificationKey:
    kid: str
    public_key: bytes = field(repr=False)
    activated_at: datetime
    retired_from_signing_at: datetime | None
    verify_until: datetime | None

    def may_verify_at(self, now: datetime) -> bool:
        if now < self.activated_at:
            return False
        if self.retired_from_signing_at is None:
            return True
        return (
            self.retired_from_signing_at <= now
            and self.verify_until is not None
            and now < self.verify_until
        )


@dataclass(frozen=True, slots=True)
class JwtKeyRing:
    """Validated immutable RS256 signing and verification snapshot."""

    ring_version: str
    active_signing_kid: str
    private_key: bytes = field(repr=False)
    keys: tuple[JwtVerificationKey, ...]

    minimum_previous_overlap_seconds = 960
    _root_fields = frozenset({"ring_version", "active_signing_kid", "keys"})
    _key_fields = frozenset(
        {
            "kid",
            "public_key_file",
            "private_key_file",
            "activated_at",
            "retired_from_signing_at",
            "verify_until",
        }
    )

    @classmethod
    def load(cls, manifest_file: Path, *, now: datetime | None = None) -> JwtKeyRing:
        """Load a complete ring or fail without retaining a partial configuration."""
        try:
            document = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError("JWT key ring manifest is unreadable or invalid JSON") from error
        if not isinstance(document, dict) or set(document) != cls._root_fields:
            raise RuntimeError("JWT key ring manifest root schema is invalid")
        ring_version = cls._required_identifier(document, "ring_version")
        active_kid = cls._required_identifier(document, "active_signing_kid")
        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list) or not raw_keys:
            raise RuntimeError("JWT key ring must contain at least one key")

        effective_now = cls._normalize_now(now)
        resolved_keys: list[JwtVerificationKey] = []
        seen_kids: set[str] = set()
        active_private_key: bytes | None = None
        active_matches = 0
        for raw_key in raw_keys:
            if (
                not isinstance(raw_key, dict)
                or not {
                    "kid",
                    "public_key_file",
                    "activated_at",
                }.issubset(raw_key)
                or not set(raw_key).issubset(cls._key_fields)
            ):
                raise RuntimeError("JWT key ring entry schema is invalid")
            kid = cls._required_identifier(raw_key, "kid")
            if kid in seen_kids:
                raise RuntimeError("JWT key ring kid values must be unique")
            seen_kids.add(kid)
            activated_at = cls._utc_timestamp(raw_key, "activated_at", required=True)
            assert activated_at is not None
            retired_at = cls._utc_timestamp(raw_key, "retired_from_signing_at", required=False)
            verify_until = cls._utc_timestamp(raw_key, "verify_until", required=False)
            if (retired_at is None) != (verify_until is None):
                raise RuntimeError("JWT previous key retirement timestamps must be paired")
            if retired_at is not None:
                if retired_at < activated_at:
                    raise RuntimeError("JWT key retirement precedes activation")
                assert verify_until is not None
                overlap = (verify_until - retired_at).total_seconds()
                if overlap < cls.minimum_previous_overlap_seconds:
                    raise RuntimeError("JWT previous key verification overlap is insufficient")

            public_bytes, public_key = cls._load_public_key(
                cls._resolve_key_path(manifest_file, raw_key, "public_key_file")
            )
            private_value = raw_key.get("private_key_file")
            if private_value is not None and not isinstance(private_value, str):
                raise RuntimeError("JWT private key file reference is invalid")
            private_bytes: bytes | None = None
            private_key: RSAPrivateKey | None = None
            if isinstance(private_value, str):
                private_bytes, private_key = cls._load_private_key(
                    cls._resolve_key_path(manifest_file, raw_key, "private_key_file")
                )

            if kid == active_kid:
                active_matches += 1
                if retired_at is not None or activated_at > effective_now:
                    raise RuntimeError("JWT active signing key is not currently active")
                if private_key is None or private_bytes is None:
                    raise RuntimeError("JWT active signing key requires private key material")
                if private_key.public_key().public_numbers() != public_key.public_numbers():
                    raise RuntimeError("JWT active signing public and private keys do not match")
                active_private_key = private_bytes
            elif retired_at is not None:
                if private_key is not None:
                    raise RuntimeError(
                        "JWT previous verification keys must not retain private keys"
                    )
            elif activated_at <= effective_now:
                raise RuntimeError("JWT non-active key must be previous or staged for future use")

            resolved_keys.append(
                JwtVerificationKey(
                    kid=kid,
                    public_key=public_bytes,
                    activated_at=activated_at,
                    retired_from_signing_at=retired_at,
                    verify_until=verify_until,
                )
            )
        if active_matches != 1 or active_private_key is None:
            raise RuntimeError("JWT active signing kid must resolve exactly once")
        return cls(ring_version, active_kid, active_private_key, tuple(resolved_keys))

    def verification_key(self, kid: str, *, now: datetime | None = None) -> bytes | None:
        effective_now = self._normalize_now(now)
        for key in self.keys:
            if key.kid != kid:
                continue
            if key.kid == self.active_signing_kid:
                return key.public_key if key.may_verify_at(effective_now) else None
            # staged key 仅用于预分发; 到达 activated_at 后也必须显式切换 active_signing_kid.
            if key.retired_from_signing_at is not None and key.may_verify_at(effective_now):
                return key.public_key
            return None
        return None

    @staticmethod
    def _normalize_now(now: datetime | None) -> datetime:
        value = now or datetime.now(UTC)
        if value.tzinfo is None:
            raise RuntimeError("JWT key ring validation time must be timezone-aware UTC")
        return value.astimezone(UTC)

    @staticmethod
    def _required_identifier(document: dict[str, Any], field: str) -> str:
        value = document.get(field)
        if not isinstance(value, str) or not value or len(value) > 128:
            raise RuntimeError(f"JWT key ring {field} is invalid")
        return value

    @staticmethod
    def _utc_timestamp(document: dict[str, Any], field: str, *, required: bool) -> datetime | None:
        value = document.get(field)
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
            raise RuntimeError(f"JWT key ring {field} must be an ISO UTC timestamp")
        try:
            normalized = value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            raise RuntimeError(f"JWT key ring {field} must be an ISO UTC timestamp") from error
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise RuntimeError(f"JWT key ring {field} must be an ISO UTC timestamp")
        return parsed.astimezone(UTC)

    @staticmethod
    def _resolve_key_path(manifest_file: Path, document: dict[str, Any], field: str) -> Path:
        value = document.get(field)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"JWT key ring {field} is invalid")
        path = Path(value)
        return path if path.is_absolute() else manifest_file.resolve().parent / path

    @staticmethod
    def _load_public_key(path: Path) -> tuple[bytes, RSAPublicKey]:
        try:
            value = path.read_bytes()
            key = serialization.load_pem_public_key(value)
        except (OSError, ValueError, TypeError) as error:
            raise RuntimeError("JWT public key material is unreadable or invalid") from error
        if not isinstance(key, RSAPublicKey):
            raise RuntimeError("JWT public key must be RSA")
        return value, key

    @staticmethod
    def _load_private_key(path: Path) -> tuple[bytes, RSAPrivateKey]:
        try:
            value = path.read_bytes()
            key = serialization.load_pem_private_key(value, password=None)
        except (OSError, ValueError, TypeError) as error:
            raise RuntimeError("JWT private key material is unreadable or invalid") from error
        if not isinstance(key, RSAPrivateKey):
            raise RuntimeError("JWT private key must be RSA")
        return value, key


class JwtService:
    issuer = "ai-auto-test-platform"
    audience = "ai-auto-test-platform-api"
    ttl_seconds = 900
    clock_skew_seconds = 60

    def __init__(self, key_ring: JwtKeyRing):
        self._key_ring = key_ring

    @property
    def ring_version(self) -> str:
        return self._key_ring.ring_version

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
            self._key_ring.private_key,
            algorithm="RS256",
            headers={"kid": self._key_ring.active_signing_kid},
        )

    def decode(self, token: str, *, now: datetime | None = None) -> AccessClaims:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not isinstance(kid, str) or header.get("alg") != "RS256":
                raise PlatformError(
                    title="Invalid access token",
                    detail="The access token is invalid.",
                    status=401,
                    code="AUTH_TOKEN_INVALID",
                )
            public_key = self._key_ring.verification_key(kid, now=now)
            if public_key is None:
                raise PlatformError(
                    title="Invalid access token",
                    detail="The access token is invalid.",
                    status=401,
                    code="AUTH_TOKEN_INVALID",
                )
            payload = jwt.decode(
                token,
                public_key,
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
