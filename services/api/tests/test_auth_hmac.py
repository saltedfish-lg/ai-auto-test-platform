from __future__ import annotations

import base64
import json
import secrets
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from platform_api.auth_hmac import AuthHmacKeyRing


@pytest.fixture
def hmac_directory() -> Iterator[Path]:
    directory = Path.cwd() / ".runtime" / f"hmac-test-{secrets.token_hex(8)}"
    directory.mkdir(parents=True, exist_ok=False)
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


def _material(byte: bytes) -> str:
    return base64.urlsafe_b64encode(byte * 32).rstrip(b"=").decode()


def _write(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_hmac_key_ring_derives_distinct_domains_and_accepts_previous(
    hmac_directory: Path,
) -> None:
    ring = AuthHmacKeyRing.load(
        _write(
            hmac_directory / "hmac.json",
            {
                "ring_version": "rotation-2",
                "active_key_id": "active-2",
                "keys": [
                    {
                        "key_id": "active-2",
                        "key_material": _material(b"a"),
                        "activated_at": "2026-08-10T00:00:00Z",
                    },
                    {
                        "key_id": "previous-1",
                        "key_material": _material(b"p"),
                        "activated_at": "2026-08-01T00:00:00Z",
                        "retired_at": "2026-08-10T00:00:00Z",
                        "accept_until": "2026-08-12T00:00:00Z",
                    },
                ],
            },
        ),
        now=datetime(2026, 8, 11, tzinfo=UTC),
    )

    rate_digests = ring.digests(
        "source-rate-limit", b"192.0.2.1", now=datetime(2026, 8, 11, tzinfo=UTC)
    )
    fingerprint_digests = ring.digests(
        "change-password-fingerprint",
        b"framed-request",
        now=datetime(2026, 8, 11, tzinfo=UTC),
    )
    assert len(rate_digests) == 2
    assert len(fingerprint_digests) == 2
    assert rate_digests[0] != fingerprint_digests[0]
    assert "material" not in repr(ring)


def test_malformed_json_longer_than_master_key_minimum_fails_closed(
    hmac_directory: Path,
) -> None:
    path = hmac_directory / "malformed.json"
    path.write_text("{" + "x" * 128, encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid JSON"):
        AuthHmacKeyRing.load(path)


def test_previous_key_with_future_retirement_is_rejected(hmac_directory: Path) -> None:
    path = _write(
        hmac_directory / "future-retirement.json",
        {
            "ring_version": "rotation-2",
            "active_key_id": "active-2",
            "keys": [
                {
                    "key_id": "active-2",
                    "key_material": _material(b"a"),
                    "activated_at": "2026-08-10T00:00:00Z",
                },
                {
                    "key_id": "previous-1",
                    "key_material": _material(b"p"),
                    "activated_at": "2026-08-01T00:00:00Z",
                    "retired_at": "2026-08-12T00:00:00Z",
                    "accept_until": "2026-08-14T00:00:00Z",
                },
            ],
        },
    )

    with pytest.raises(RuntimeError, match="retirement is in the future"):
        AuthHmacKeyRing.load(path, now=datetime(2026, 8, 11, tzinfo=UTC))
