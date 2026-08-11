from __future__ import annotations

import base64
import json
import re
import secrets
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from argon2 import PasswordHasher, Type
from platform_api import keygen as keygen_module
from platform_api.audit import AuditContext
from platform_api.auth_service import (
    GENERIC_RBAC_CONDITION,
    REVIEW_RBAC_CONDITION,
    SUPER_ADMIN_RBAC_CONDITION,
    AuthenticationService,
    AuthorizationContext,
)
from platform_api.errors import PlatformError
from platform_api.keygen import DevelopmentKeyRingPaths, generate_development_key_ring
from platform_api.security import (
    AccessClaims,
    JwtKeyRing,
    JwtService,
    PasswordPolicyError,
    PasswordService,
    new_refresh_token,
    new_ulid,
    refresh_token_hash,
)


def _valid_password() -> str:
    return f"A{secrets.token_hex(10)}9"


@pytest.fixture
def key_directory() -> Iterator[Path]:
    runtime_root = (Path.cwd() / ".runtime").resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    directory = runtime_root / f"auth-security-{secrets.token_hex(8)}"
    directory.mkdir(exist_ok=False)
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


def _generated_ring(directory: Path, kid: str) -> DevelopmentKeyRingPaths:
    return generate_development_key_ring(
        directory,
        kid=kid,
        ring_version=f"test-{kid}",
    )


def _manifest(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_manifest(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_argon2id_policy_hash_and_verification() -> None:
    service = PasswordService()
    password = _valid_password()
    service.validate(password, "admin")
    encoded = service.hash(password)

    assert service.verify(encoded, password)
    assert not service.verify(encoded, _valid_password())
    assert encoded.startswith("$argon2id$v=19$m=65536,t=3,p=1$")


def test_argon2id_rehash_never_downgrades_stronger_parameters() -> None:
    password = _valid_password()
    stronger_hash = PasswordHasher(
        time_cost=4,
        memory_cost=131072,
        parallelism=2,
        hash_len=64,
        salt_len=32,
        type=Type.ID,
    ).hash(password)
    service = PasswordService()

    assert service.verify(stronger_hash, password)
    assert not service.needs_rehash(stronger_hash)


@pytest.mark.parametrize(
    ("candidate", "username"),
    [
        ("short9A", "operator"),
        ("abcdefghijkl", "operator"),
        ("123456789012", "operator"),
        (" admin1234567", "operator"),
        ("Admin0000000", "admin0000000"),
    ],
)
def test_password_policy_rejects_frozen_invalid_classes(candidate: str, username: str) -> None:
    with pytest.raises(PasswordPolicyError):
        PasswordService().validate(candidate, username)


def test_versioned_common_password_denylist_rejects_upgradeable_entry() -> None:
    with pytest.raises(PasswordPolicyError, match="common-password denylist"):
        PasswordService().validate("ILoveYou1234", "operator")


def test_refresh_token_is_32_random_bytes_and_only_sha256_is_persistable() -> None:
    token = new_refresh_token()
    padded = token + "=" * (-len(token) % 4)
    assert len(base64.urlsafe_b64decode(padded)) == 32
    assert len(refresh_token_hash(token)) == 32
    assert token.encode() != refresh_token_hash(token)


@pytest.mark.parametrize("token", ["not-base64url", "x" * 42, "x" * 44, "密" * 43])
def test_refresh_token_hash_rejects_noncanonical_values(token: str) -> None:
    with pytest.raises(ValueError, match="invalid refresh token format"):
        refresh_token_hash(token)


def test_logout_does_not_open_audit_transaction_until_session_resolves() -> None:
    class EmptySession:
        def __enter__(self) -> EmptySession:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def scalar(self, _: object) -> None:
            return None

    class SessionFactoryProbe:
        opened = 0

        def __call__(self) -> EmptySession:
            self.opened += 1
            return EmptySession()

    factory = SessionFactoryProbe()
    service = object.__new__(AuthenticationService)
    service._session_factory = factory  # type: ignore[assignment]
    context = AuditContext("logout-unit", "unit-source")

    service.logout(None, context)
    service.logout("not-base64url", context)
    assert factory.opened == 0

    service.logout(new_refresh_token(), context)
    assert factory.opened == 1


def test_ulid_is_crockford_and_26_characters() -> None:
    assert re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", new_ulid())


def test_rs256_access_claims_have_no_permission_snapshot(key_directory: Path) -> None:
    generated = _generated_ring(key_directory, "test-kid")
    service = JwtService(JwtKeyRing.load(generated.manifest_file))
    claims = AccessClaims(new_ulid(), new_ulid(), 3)
    token = service.issue(claims)
    payload = jwt.decode(token, options={"verify_signature": False})

    assert service.decode(token) == claims
    assert payload["token_use"] == "access"
    assert "permissions" not in payload
    assert "roles" not in payload


def test_wrong_kid_is_rejected(key_directory: Path) -> None:
    issuer_ring = _generated_ring(key_directory / "issuer", "issuer-kid")
    verifier_ring = _generated_ring(key_directory / "verifier", "verifier-kid")
    issuer = JwtService(JwtKeyRing.load(issuer_ring.manifest_file))
    verifier = JwtService(JwtKeyRing.load(verifier_ring.manifest_file))
    token = issuer.issue(AccessClaims(new_ulid(), new_ulid(), 1))

    with pytest.raises(PlatformError) as captured:
        verifier.decode(token)

    assert captured.value.code == "AUTH_TOKEN_INVALID"


def test_key_ring_rotation_keeps_previous_token_during_overlap(key_directory: Path) -> None:
    old = _generated_ring(key_directory / "old", "old-kid")
    new = _generated_ring(key_directory / "new", "new-kid")
    old_service = JwtService(JwtKeyRing.load(old.manifest_file))
    claims = AccessClaims(new_ulid(), new_ulid(), 1)
    old_token = old_service.issue(claims)
    now = datetime.now(UTC)
    old_key = _manifest(old.manifest_file)["keys"]
    new_key = _manifest(new.manifest_file)["keys"]
    assert isinstance(old_key, list) and isinstance(new_key, list)
    old_entry = dict(old_key[0])
    new_entry = dict(new_key[0])
    old_entry.pop("private_key_file")
    old_entry["public_key_file"] = str(old.public_key_file)
    retired_at = now - timedelta(seconds=1)
    old_entry["activated_at"] = (retired_at - timedelta(days=1)).isoformat()
    old_entry["retired_from_signing_at"] = retired_at.isoformat()
    old_entry["verify_until"] = (retired_at + timedelta(seconds=960)).isoformat()
    new_entry["public_key_file"] = str(new.public_key_file)
    new_entry["private_key_file"] = str(new.private_key_file)
    rotated_manifest = _write_manifest(
        key_directory / "rotated.json",
        {
            "ring_version": "rotation-v2",
            "active_signing_kid": "new-kid",
            "keys": [old_entry, new_entry],
        },
    )
    rotated = JwtService(JwtKeyRing.load(rotated_manifest, now=now))

    assert rotated.ring_version == "rotation-v2"
    assert rotated.decode(old_token, now=now) == claims
    assert jwt.get_unverified_header(rotated.issue(claims))["kid"] == "new-kid"


def test_staged_key_never_verifies_until_manifest_switches_active(key_directory: Path) -> None:
    current = _generated_ring(key_directory / "current", "current-kid")
    staged = _generated_ring(key_directory / "staged", "staged-kid")
    claims = AccessClaims(new_ulid(), new_ulid(), 1)
    staged_token = JwtService(JwtKeyRing.load(staged.manifest_file)).issue(claims)
    current_keys = _manifest(current.manifest_file)["keys"]
    staged_keys = _manifest(staged.manifest_file)["keys"]
    assert isinstance(current_keys, list) and isinstance(staged_keys, list)
    current_entry = dict(current_keys[0])
    staged_entry = dict(staged_keys[0])
    current_entry["public_key_file"] = str(current.public_key_file)
    current_entry["private_key_file"] = str(current.private_key_file)
    staged_entry.pop("private_key_file")
    staged_entry["public_key_file"] = str(staged.public_key_file)
    now = datetime.now(UTC)
    activation = now + timedelta(seconds=60)
    staged_entry["activated_at"] = activation.isoformat()
    staged_manifest = _write_manifest(
        key_directory / "staged-manifest.json",
        {
            "ring_version": "staged-v1",
            "active_signing_kid": "current-kid",
            "keys": [current_entry, staged_entry],
        },
    )
    verifier = JwtService(JwtKeyRing.load(staged_manifest, now=now))

    for verification_time in (now, activation + timedelta(seconds=1)):
        with pytest.raises(PlatformError) as captured:
            verifier.decode(staged_token, now=verification_time)
        assert captured.value.code == "AUTH_TOKEN_INVALID"

    switched_current = dict(current_entry)
    switched_current.pop("private_key_file")
    retired_at = activation + timedelta(seconds=1)
    switched_current["retired_from_signing_at"] = retired_at.isoformat()
    switched_current["verify_until"] = (retired_at + timedelta(seconds=960)).isoformat()
    switched_staged = dict(staged_entry)
    switched_staged["private_key_file"] = str(staged.private_key_file)
    switched_manifest = _write_manifest(
        key_directory / "switched-manifest.json",
        {
            "ring_version": "staged-v2",
            "active_signing_kid": "staged-kid",
            "keys": [switched_current, switched_staged],
        },
    )
    switched = JwtService(JwtKeyRing.load(switched_manifest, now=retired_at))

    assert switched.decode(staged_token, now=retired_at) == claims


def test_previous_key_cannot_verify_before_its_retirement_boundary(
    key_directory: Path,
) -> None:
    previous = _generated_ring(key_directory / "previous", "previous-kid")
    active = _generated_ring(key_directory / "active", "active-kid")
    claims = AccessClaims(new_ulid(), new_ulid(), 1)
    previous_token = JwtService(JwtKeyRing.load(previous.manifest_file)).issue(claims)
    previous_keys = _manifest(previous.manifest_file)["keys"]
    active_keys = _manifest(active.manifest_file)["keys"]
    assert isinstance(previous_keys, list) and isinstance(active_keys, list)
    previous_entry = dict(previous_keys[0])
    active_entry = dict(active_keys[0])
    previous_entry.pop("private_key_file")
    previous_entry["public_key_file"] = str(previous.public_key_file)
    active_entry["public_key_file"] = str(active.public_key_file)
    active_entry["private_key_file"] = str(active.private_key_file)
    now = datetime.now(UTC)
    retirement = now + timedelta(seconds=60)
    previous_entry["retired_from_signing_at"] = retirement.isoformat()
    previous_entry["verify_until"] = (retirement + timedelta(seconds=960)).isoformat()
    manifest = _write_manifest(
        key_directory / "future-retirement.json",
        {
            "ring_version": "future-retirement-v1",
            "active_signing_kid": "active-kid",
            "keys": [previous_entry, active_entry],
        },
    )
    verifier = JwtService(JwtKeyRing.load(manifest, now=now))

    with pytest.raises(PlatformError) as captured:
        verifier.decode(previous_token, now=now)

    assert captured.value.code == "AUTH_TOKEN_INVALID"
    assert verifier.decode(previous_token, now=retirement) == claims


def test_key_ring_rejects_retired_previous_token(key_directory: Path) -> None:
    old = _generated_ring(key_directory / "old", "old-kid")
    new = _generated_ring(key_directory / "new", "new-kid")
    claims = AccessClaims(new_ulid(), new_ulid(), 1)
    old_token = JwtService(JwtKeyRing.load(old.manifest_file)).issue(claims)
    now = datetime.now(UTC)
    old_keys = _manifest(old.manifest_file)["keys"]
    new_keys = _manifest(new.manifest_file)["keys"]
    assert isinstance(old_keys, list) and isinstance(new_keys, list)
    old_entry = dict(old_keys[0])
    new_entry = dict(new_keys[0])
    old_entry.pop("private_key_file")
    old_entry["public_key_file"] = str(old.public_key_file)
    retired_at = now - timedelta(seconds=961)
    old_entry["activated_at"] = (retired_at - timedelta(days=1)).isoformat()
    old_entry["retired_from_signing_at"] = retired_at.isoformat()
    old_entry["verify_until"] = (retired_at + timedelta(seconds=960)).isoformat()
    new_entry["public_key_file"] = str(new.public_key_file)
    new_entry["private_key_file"] = str(new.private_key_file)
    manifest = _write_manifest(
        key_directory / "retired.json",
        {
            "ring_version": "rotation-v3",
            "active_signing_kid": "new-kid",
            "keys": [old_entry, new_entry],
        },
    )
    verifier = JwtService(JwtKeyRing.load(manifest, now=now))

    with pytest.raises(PlatformError) as captured:
        verifier.decode(old_token, now=now)

    assert captured.value.code == "AUTH_TOKEN_INVALID"


def test_key_ring_rejects_duplicate_kid_and_short_overlap(key_directory: Path) -> None:
    active = _generated_ring(key_directory / "active", "active-kid")
    previous = _generated_ring(key_directory / "previous", "previous-kid")
    active_keys = _manifest(active.manifest_file)["keys"]
    previous_keys = _manifest(previous.manifest_file)["keys"]
    assert isinstance(active_keys, list) and isinstance(previous_keys, list)
    active_entry = dict(active_keys[0])
    active_entry["public_key_file"] = str(active.public_key_file)
    active_entry["private_key_file"] = str(active.private_key_file)
    duplicate = dict(active_entry)
    duplicate.pop("private_key_file")
    duplicate["public_key_file"] = str(previous.public_key_file)
    now = datetime.now(UTC)
    duplicate["retired_from_signing_at"] = now.isoformat()
    duplicate["verify_until"] = (now + timedelta(seconds=960)).isoformat()
    duplicate_manifest = _write_manifest(
        key_directory / "duplicate.json",
        {
            "ring_version": "invalid-duplicate",
            "active_signing_kid": "active-kid",
            "keys": [active_entry, duplicate],
        },
    )
    with pytest.raises(RuntimeError, match="unique"):
        JwtKeyRing.load(duplicate_manifest, now=now)

    previous_entry = dict(previous_keys[0])
    previous_entry.pop("private_key_file")
    previous_entry["public_key_file"] = str(previous.public_key_file)
    previous_entry["retired_from_signing_at"] = now.isoformat()
    previous_entry["verify_until"] = (now + timedelta(seconds=959)).isoformat()
    short_manifest = _write_manifest(
        key_directory / "short-overlap.json",
        {
            "ring_version": "invalid-overlap",
            "active_signing_kid": "active-kid",
            "keys": [active_entry, previous_entry],
        },
    )
    with pytest.raises(RuntimeError, match="overlap"):
        JwtKeyRing.load(short_manifest, now=now)


def test_key_ring_rejects_non_utc_time_and_mismatched_key_pair(key_directory: Path) -> None:
    active = _generated_ring(key_directory / "active", "active-kid")
    other = _generated_ring(key_directory / "other", "other-kid")
    active_keys = _manifest(active.manifest_file)["keys"]
    assert isinstance(active_keys, list)
    entry = dict(active_keys[0])
    entry["public_key_file"] = str(active.public_key_file)
    entry["private_key_file"] = str(active.private_key_file)
    entry["activated_at"] = "2026-08-10T12:00:00+08:00"
    non_utc_manifest = _write_manifest(
        key_directory / "non-utc.json",
        {
            "ring_version": "invalid-time",
            "active_signing_kid": "active-kid",
            "keys": [entry],
        },
    )
    with pytest.raises(RuntimeError, match="ISO UTC"):
        JwtKeyRing.load(non_utc_manifest)

    entry["activated_at"] = datetime.now(UTC).isoformat()
    entry["private_key_file"] = str(other.private_key_file)
    mismatch_manifest = _write_manifest(
        key_directory / "mismatch.json",
        {
            "ring_version": "invalid-pair",
            "active_signing_kid": "active-kid",
            "keys": [entry],
        },
    )
    with pytest.raises(RuntimeError, match="do not match"):
        JwtKeyRing.load(mismatch_manifest)


def test_development_manifest_contains_paths_but_no_key_material(key_directory: Path) -> None:
    generated = _generated_ring(key_directory, "manifest-kid")
    manifest_text = generated.manifest_file.read_text(encoding="utf-8")

    assert generated.ring_version in manifest_text
    assert generated.kid in manifest_text
    assert "BEGIN PRIVATE KEY" not in manifest_text
    assert "BEGIN PUBLIC KEY" not in manifest_text


def test_key_ring_repr_never_contains_pem_material(key_directory: Path) -> None:
    generated = _generated_ring(key_directory, "repr-kid")
    ring = JwtKeyRing.load(generated.manifest_file)
    private_pem = generated.private_key_file.read_text(encoding="ascii")
    public_pem = generated.public_key_file.read_text(encoding="ascii")

    ring_repr = repr(ring)
    verification_key_repr = repr(ring.keys[0])
    assert "BEGIN PRIVATE KEY" not in ring_repr
    assert "BEGIN PUBLIC KEY" not in ring_repr
    assert "BEGIN PUBLIC KEY" not in verification_key_repr
    assert private_pem not in ring_repr
    assert public_pem not in ring_repr
    assert public_pem not in verification_key_repr


def test_keygen_cleans_private_key_when_public_key_creation_fails(
    key_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_create = keygen_module._create_exclusive

    def fail_public(path: Path, mode: int, created_paths: list[Path]) -> int:
        if path.name == "jwt-public-failure-public.pem":
            raise OSError("public key creation failed")
        return original_create(path, mode, created_paths)

    monkeypatch.setattr(keygen_module, "_create_exclusive", fail_public)
    with pytest.raises(OSError, match="public key creation failed"):
        generate_development_key_ring(key_directory, kid="public-failure")
    assert list(key_directory.iterdir()) == []

    monkeypatch.setattr(keygen_module, "_create_exclusive", original_create)
    generated = generate_development_key_ring(key_directory, kid="public-failure")
    assert generated.manifest_file.is_file()
    assert generated.private_key_file.is_file()
    assert generated.public_key_file.is_file()


def test_keygen_cleans_key_files_when_manifest_creation_fails(
    key_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_create = keygen_module._create_exclusive

    def fail_manifest(path: Path, mode: int, created_paths: list[Path]) -> int:
        if path.name == "jwt-key-ring.json":
            raise OSError("manifest creation failed")
        return original_create(path, mode, created_paths)

    monkeypatch.setattr(keygen_module, "_create_exclusive", fail_manifest)
    with pytest.raises(OSError, match="manifest creation failed"):
        generate_development_key_ring(key_directory, kid="manifest-create-failure")
    assert list(key_directory.iterdir()) == []

    monkeypatch.setattr(keygen_module, "_create_exclusive", original_create)
    generated = generate_development_key_ring(key_directory, kid="manifest-create-failure")
    assert generated.manifest_file.is_file()
    assert generated.private_key_file.is_file()
    assert generated.public_key_file.is_file()


def test_keygen_cleans_partial_manifest_and_preserves_write_error(
    key_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write_manifest = keygen_module._write_manifest
    failure = OSError("manifest write failed")

    def fail_manifest_write(descriptor: int, manifest: dict[str, object]) -> None:
        del manifest
        keygen_module.os.write(descriptor, b"{")
        keygen_module.os.close(descriptor)
        raise failure

    monkeypatch.setattr(keygen_module, "_write_manifest", fail_manifest_write)
    with pytest.raises(OSError) as captured:
        generate_development_key_ring(key_directory, kid="manifest-write-failure")
    assert captured.value is failure
    assert list(key_directory.iterdir()) == []

    monkeypatch.setattr(keygen_module, "_write_manifest", original_write_manifest)
    generated = generate_development_key_ring(key_directory, kid="manifest-write-failure")
    assert generated.manifest_file.is_file()
    assert generated.private_key_file.is_file()
    assert generated.public_key_file.is_file()


def test_rbac_frozen_conditions_are_exact_and_fail_closed_without_atomic_audit() -> None:
    context = AuthorizationContext(None, "PLATFORM_ALL", None, True)

    assert AuthenticationService._condition_satisfied(GENERIC_RBAC_CONDITION, "actor", context)
    assert not AuthenticationService._condition_satisfied(REVIEW_RBAC_CONDITION, "actor", context)
    assert not AuthenticationService._condition_satisfied(
        SUPER_ADMIN_RBAC_CONDITION, "actor", context
    )
    assert not AuthenticationService._condition_satisfied(
        "unrecognized frozen condition", "actor", context
    )
