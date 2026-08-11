"""Safe local-only RS256 development key generation."""

from __future__ import annotations

import json
import os
import re
import secrets
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass(frozen=True, slots=True)
class DevelopmentKeyRingPaths:
    manifest_file: Path
    private_key_file: Path
    public_key_file: Path
    ring_version: str
    kid: str


def generate_development_key_ring(
    output_directory: Path,
    *,
    kid: str = "atp-local-rs256-v1",
    ring_version: str | None = None,
) -> DevelopmentKeyRingPaths:
    """Create an all-or-nothing local RSA key ring without overwriting existing files."""
    if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", kid) is None:
        raise ValueError("development JWT kid contains unsafe path characters")
    version = ring_version or f"local-{secrets.token_hex(8)}"
    if not version or len(version) > 128:
        raise ValueError("development JWT ring version is invalid")
    output_directory.mkdir(parents=True, exist_ok=True)
    private_path = output_directory / f"jwt-{kid}-private.pem"
    public_path = output_directory / f"jwt-{kid}-public.pem"
    manifest_path = output_directory / "jwt-key-ring.json"
    if private_path.exists() or public_path.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite existing JWT key-ring material")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_bytes = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    activated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest: dict[str, object] = {
        "ring_version": version,
        "active_signing_kid": kid,
        "keys": [
            {
                "kid": kid,
                "public_key_file": public_path.name,
                "private_key_file": private_path.name,
                "activated_at": activated_at,
            }
        ],
    }
    created_paths: list[Path] = []
    try:
        private_fd = _create_exclusive(private_path, 0o600, created_paths)
        _write_binary(private_fd, private_bytes)
        public_fd = _create_exclusive(public_path, 0o644, created_paths)
        _write_binary(public_fd, public_bytes)
        manifest_fd = _create_exclusive(manifest_path, 0o600, created_paths)
        _write_manifest(manifest_fd, manifest)
    except BaseException:
        # 仅回收本次 O_EXCL 成功创建的路径; 并发方或预存文件不会进入清单.
        for created_path in reversed(created_paths):
            # 清理失败不得覆盖触发回滚的原始生成/写入异常.
            with suppress(OSError):
                created_path.unlink(missing_ok=True)
        raise
    return DevelopmentKeyRingPaths(manifest_path, private_path, public_path, version, kid)


def _create_exclusive(path: Path, mode: int, created_paths: list[Path]) -> int:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    created_paths.append(path)
    return descriptor


def _write_binary(descriptor: int, value: bytes) -> None:
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
    except BaseException:
        _close_if_open(descriptor)
        raise


def _write_manifest(descriptor: int, manifest: dict[str, object]) -> None:
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
    except BaseException:
        _close_if_open(descriptor)
        raise


def _close_if_open(descriptor: int) -> None:
    with suppress(OSError):
        os.close(descriptor)
