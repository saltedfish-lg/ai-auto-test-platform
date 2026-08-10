"""Safe local-only RS256 development key generation."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_development_keys(output_directory: Path) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    private_path = output_directory / "jwt-private.pem"
    public_path = output_directory / "jwt-public.pem"
    if private_path.exists() or public_path.exists():
        raise FileExistsError("refusing to overwrite existing RSA key material")
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
    private_fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(private_fd, "wb") as handle:
        handle.write(private_bytes)
    public_fd = os.open(public_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(public_fd, "wb") as handle:
        handle.write(public_bytes)
    return private_path, public_path
