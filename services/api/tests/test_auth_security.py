from __future__ import annotations

import base64
import re
import secrets
from collections.abc import Iterator
from pathlib import Path

import jwt
import pytest
from argon2 import PasswordHasher, Type
from platform_api.auth_service import (
    GENERIC_RBAC_CONDITION,
    REVIEW_RBAC_CONDITION,
    SUPER_ADMIN_RBAC_CONDITION,
    AuthenticationService,
    AuthorizationContext,
)
from platform_api.errors import PlatformError
from platform_api.keygen import generate_development_keys
from platform_api.security import (
    AccessClaims,
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
        for child in directory.iterdir():
            if child.is_file():
                child.unlink()
        directory.rmdir()


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


def test_ulid_is_crockford_and_26_characters() -> None:
    assert re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", new_ulid())


def test_rs256_access_claims_have_no_permission_snapshot(key_directory: Path) -> None:
    private_path, public_path = generate_development_keys(key_directory)
    service = JwtService(private_path, public_path, "test-kid")
    claims = AccessClaims(new_ulid(), new_ulid(), 3)
    token = service.issue(claims)
    payload = jwt.decode(token, options={"verify_signature": False})

    assert service.decode(token) == claims
    assert payload["token_use"] == "access"
    assert "permissions" not in payload
    assert "roles" not in payload


def test_wrong_kid_is_rejected(key_directory: Path) -> None:
    private_path, public_path = generate_development_keys(key_directory)
    issuer = JwtService(private_path, public_path, "issuer-kid")
    verifier = JwtService(private_path, public_path, "verifier-kid")
    token = issuer.issue(AccessClaims(new_ulid(), new_ulid(), 1))

    with pytest.raises(PlatformError) as captured:
        verifier.decode(token)

    assert captured.value.code == "AUTH_TOKEN_INVALID"


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
