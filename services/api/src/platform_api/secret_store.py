"""Envelope for encrypted model-provider credentials stored in MySQL."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretStoreError(RuntimeError):
    """Secret storage failed without exposing credential or key material."""


@dataclass(frozen=True, slots=True)
class EncryptedSecret:
    ciphertext: bytes = field(repr=False)
    key_id: str


class SecretProtector(Protocol):
    def encrypt(self, model_config_id: str, secret_value: str) -> EncryptedSecret: ...

    def decrypt(self, model_config_id: str, ciphertext: bytes, key_id: str) -> str: ...

    def encrypt_scoped(
        self, scope: str, owner_id: str, secret_value: str
    ) -> EncryptedSecret: ...

    def decrypt_scoped(
        self, scope: str, owner_id: str, ciphertext: bytes, key_id: str
    ) -> str: ...


class AesGcmSecretProtector:
    """AES-256-GCM key-ring protector with model identity bound as AAD."""

    def __init__(self, active_key_id: str, keys: dict[str, bytes]) -> None:
        if not active_key_id or len(active_key_id) > 64:
            raise SecretStoreError("The active model secret key id is invalid.")
        if active_key_id not in keys:
            raise SecretStoreError("The active model secret key is unavailable.")
        if not keys or any(len(value) != 32 for value in keys.values()):
            raise SecretStoreError("Every model secret key must contain 32 bytes.")
        self._active_key_id = active_key_id
        self._keys = dict(keys)

    @classmethod
    def load(cls, path: Path) -> AesGcmSecretProtector:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            active_key_id = document["active_key_id"]
            entries = document["keys"]
            if not isinstance(active_key_id, str) or not active_key_id:
                raise ValueError("invalid active key id")
            if not isinstance(entries, list):
                raise ValueError("invalid key list")
            keys: dict[str, bytes] = {}
            for entry in entries:
                key_id = entry["key_id"]
                encoded = entry["key_material"]
                if not isinstance(key_id, str) or not key_id or not isinstance(encoded, str):
                    raise ValueError("invalid key entry")
                if len(key_id) > 64 or key_id in keys:
                    raise ValueError("invalid or duplicate key id")
                padding = "=" * (-len(encoded) % 4)
                keys[key_id] = base64.urlsafe_b64decode(encoded + padding)
            return cls(active_key_id, keys)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise SecretStoreError("The model secret key ring could not be loaded.") from error

    @staticmethod
    def _associated_data(scope: str, owner_id: str) -> bytes:
        return f"atp:{scope}:v1:{owner_id}".encode()

    def encrypt(self, model_config_id: str, secret_value: str) -> EncryptedSecret:
        return self.encrypt_scoped("model-config-secret", model_config_id, secret_value)

    def encrypt_scoped(
        self, scope: str, owner_id: str, secret_value: str
    ) -> EncryptedSecret:
        if not secret_value:
            raise SecretStoreError("An empty model credential cannot be encrypted.")
        nonce = os.urandom(12)
        key = self._keys[self._active_key_id]
        ciphertext = nonce + AESGCM(key).encrypt(
            nonce,
            secret_value.encode("utf-8"),
            self._associated_data(scope, owner_id),
        )
        return EncryptedSecret(ciphertext=ciphertext, key_id=self._active_key_id)

    def decrypt(self, model_config_id: str, ciphertext: bytes, key_id: str) -> str:
        return self.decrypt_scoped("model-config-secret", model_config_id, ciphertext, key_id)

    def decrypt_scoped(
        self, scope: str, owner_id: str, ciphertext: bytes, key_id: str
    ) -> str:
        key = self._keys.get(key_id)
        if key is None or len(ciphertext) < 29:
            raise SecretStoreError("The model credential cannot be decrypted.")
        try:
            plaintext = AESGCM(key).decrypt(
                ciphertext[:12],
                ciphertext[12:],
                self._associated_data(scope, owner_id),
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, ValueError, UnicodeDecodeError) as error:
            raise SecretStoreError("The model credential cannot be decrypted.") from error


class UnavailableSecretProtector:
    """Fail-closed deployment state used when no model key ring is configured."""

    def encrypt(self, model_config_id: str, secret_value: str) -> EncryptedSecret:
        del model_config_id, secret_value
        raise SecretStoreError("The model secret store is not configured.")

    def decrypt(self, model_config_id: str, ciphertext: bytes, key_id: str) -> str:
        del model_config_id, ciphertext, key_id
        raise SecretStoreError("The model secret store is not configured.")

    def encrypt_scoped(
        self, scope: str, owner_id: str, secret_value: str
    ) -> EncryptedSecret:
        del scope, owner_id, secret_value
        raise SecretStoreError("The secret store is not configured.")

    def decrypt_scoped(
        self, scope: str, owner_id: str, ciphertext: bytes, key_id: str
    ) -> str:
        del scope, owner_id, ciphertext, key_id
        raise SecretStoreError("The secret store is not configured.")
