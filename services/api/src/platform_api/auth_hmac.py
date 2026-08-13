"""Fail-closed HMAC master-key loading and domain-separated derivation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_DOMAINS = frozenset(
    {"source-rate-limit", "change-password-fingerprint", "idempotency-storage-key"}
)
_MINIMUM_ROTATION_OVERLAP = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class _MasterKey:
    key_id: str
    material: bytes = field(repr=False)
    activated_at: datetime
    retired_at: datetime | None
    accept_until: datetime | None

    def accepted_at(self, now: datetime) -> bool:
        if now < self.activated_at:
            return False
        if self.retired_at is not None and now < self.retired_at:
            return False
        return self.accept_until is None or now < self.accept_until


@dataclass(frozen=True, slots=True)
class AuthHmacKeyRing:
    """Immutable snapshot that never exposes master or derived key material in repr."""

    ring_version: str
    active_key_id: str
    keys: tuple[_MasterKey, ...] = field(repr=False)

    @classmethod
    def load(cls, path: Path, *, now: datetime | None = None) -> AuthHmacKeyRing:
        effective_now = (now or datetime.now(UTC)).astimezone(UTC)
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise RuntimeError("authentication HMAC master-key file is unreadable") from error
        if not raw:
            raise RuntimeError("authentication HMAC master-key file is empty")
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError("authentication HMAC key ring is invalid JSON") from error
        if not isinstance(document, dict) or set(document) != {
            "ring_version",
            "active_key_id",
            "keys",
        }:
            raise RuntimeError("authentication HMAC key ring schema is invalid")
        ring_version = cls._identifier(document.get("ring_version"), "ring_version")
        active_key_id = cls._identifier(document.get("active_key_id"), "active_key_id")
        entries = document.get("keys")
        if not isinstance(entries, list) or not entries:
            raise RuntimeError("authentication HMAC key ring has no keys")
        keys: list[_MasterKey] = []
        seen: set[str] = set()
        active_matches = 0
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or not {
                    "key_id",
                    "key_material",
                    "activated_at",
                }.issubset(entry)
                or not set(entry).issubset(
                    {"key_id", "key_material", "activated_at", "retired_at", "accept_until"}
                )
            ):
                raise RuntimeError("authentication HMAC key entry schema is invalid")
            key_id = cls._identifier(entry.get("key_id"), "key_id")
            if key_id in seen:
                raise RuntimeError("authentication HMAC key ids must be unique")
            seen.add(key_id)
            material = cls._decode_material(entry.get("key_material"))
            activated_at = cls._timestamp(entry.get("activated_at"), required=True)
            assert activated_at is not None
            retired_at = cls._timestamp(entry.get("retired_at"), required=False)
            accept_until = cls._timestamp(entry.get("accept_until"), required=False)
            if (retired_at is None) != (accept_until is None):
                raise RuntimeError("authentication HMAC retirement timestamps must be paired")
            if retired_at is not None:
                assert accept_until is not None
                if (
                    retired_at < activated_at
                    or accept_until - retired_at < _MINIMUM_ROTATION_OVERLAP
                ):
                    raise RuntimeError("authentication HMAC rotation overlap is insufficient")
            if key_id == active_key_id:
                active_matches += 1
                if retired_at is not None or activated_at > effective_now:
                    raise RuntimeError("authentication HMAC active key is not active")
            elif retired_at is None and activated_at <= effective_now:
                raise RuntimeError("non-active HMAC key must be previous or staged")
            elif retired_at is not None and retired_at > effective_now:
                raise RuntimeError("authentication HMAC previous key retirement is in the future")
            keys.append(_MasterKey(key_id, material, activated_at, retired_at, accept_until))
        if active_matches != 1:
            raise RuntimeError("authentication HMAC active key must resolve exactly once")
        return cls(ring_version, active_key_id, tuple(keys))

    def digests(
        self, domain: str, value: bytes, *, now: datetime | None = None
    ) -> tuple[bytes, ...]:
        """Return active then accepted-previous digests for safe rotation overlap."""
        effective_now = (now or datetime.now(UTC)).astimezone(UTC)
        ordered = sorted(self.keys, key=lambda key: key.key_id != self.active_key_id)
        return tuple(
            hmac.new(self._derive(key.material, domain), value, hashlib.sha256).digest()
            for key in ordered
            if key.accepted_at(effective_now)
            and (key.key_id == self.active_key_id or key.retired_at is not None)
        )

    def hex_digests(self, domain: str, value: bytes) -> tuple[str, ...]:
        return tuple(digest.hex() for digest in self.digests(domain, value))

    @staticmethod
    def _derive(material: bytes, domain: str) -> bytes:
        if domain not in _DOMAINS:
            raise ValueError("unsupported authentication HMAC domain")
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ai-auto-test-platform/auth-hmac/v1",
            info=b"atp-auth/" + domain.encode("ascii"),
        ).derive(material)

    @staticmethod
    def _identifier(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 128:
            raise RuntimeError(f"authentication HMAC {field_name} is invalid")
        return value

    @staticmethod
    def _decode_material(value: Any) -> bytes:
        if not isinstance(value, str):
            raise RuntimeError("authentication HMAC key material is invalid")
        try:
            material = base64.b64decode(
                value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
            )
        except (ValueError, UnicodeEncodeError) as error:
            raise RuntimeError("authentication HMAC key material is invalid") from error
        if len(material) < 32:
            raise RuntimeError("authentication HMAC master key is too short")
        return material

    @staticmethod
    def _timestamp(value: Any, *, required: bool) -> datetime | None:
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
            raise RuntimeError("authentication HMAC timestamps must be UTC")
        try:
            parsed = datetime.fromisoformat(
                value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
            )
        except ValueError as error:
            raise RuntimeError("authentication HMAC timestamps must be UTC") from error
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise RuntimeError("authentication HMAC timestamps must be UTC")
        return parsed.astimezone(UTC)
