"""Local Runner Agent identity storage; Windows uses user-scoped DPAPI."""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredAgentIdentity:
    runner_id: str
    agent_token: str
    token_version: int


class AgentCredentialStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> StoredAgentIdentity | None:
        if not self._path.exists():
            return None
        envelope = json.loads(self._path.read_text(encoding="utf-8"))
        protected = base64.b64decode(envelope["protected"])
        plaintext = _unprotect(protected)
        try:
            return StoredAgentIdentity(**json.loads(plaintext.decode("utf-8")))
        finally:
            plaintext = b""

    def save(self, identity: StoredAgentIdentity) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(asdict(identity), separators=(",", ":")).encode("utf-8")
        protected = _protect(plaintext)
        envelope = json.dumps(
            {
                "format": "WINDOWS_DPAPI_USER" if os.name == "nt" else "OWNER_ONLY",
                "protected": base64.b64encode(protected).decode("ascii"),
            },
            separators=(",", ":"),
        )
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(envelope, encoding="utf-8")
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(self._path)


class _DataBlob(ctypes.Structure):
    _fields_ = [  # noqa: RUF012
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(value: bytes) -> bytes:
    if os.name != "nt":
        return value
    source, source_buffer = _blob(value)
    result = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source),
        "Runner Agent identity",
        None,
        None,
        None,
        0x1,
        ctypes.byref(result),
    ):
        raise OSError("Runner Agent credential protection failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del source_buffer


def _unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        return value
    source, source_buffer = _blob(value)
    result = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(result)
    ):
        raise OSError("Runner Agent credential decryption failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del source_buffer
