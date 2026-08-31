"""Minimal outbound HTTP client for enrollment, heartbeat, and capability reporting."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class PlatformTransportError(RuntimeError):
    def __init__(self, status: int | None, code: str) -> None:
        super().__init__(f"Runner platform request failed: {code}")
        self.status = status
        self.code = code


@dataclass(frozen=True)
class RegistrationResult:
    runner_id: str
    agent_token: str
    token_version: int


class HttpPlatformTransport:
    def __init__(self, platform_url: str, timeout_seconds: float = 15.0) -> None:
        self._platform_url = platform_url.rstrip("/") + "/"
        self._timeout_seconds = timeout_seconds

    async def register(
        self,
        enrollment_credential: str,
        machine_fingerprint: str,
        agent_version: str,
        runtime_metadata: dict[str, object],
        capabilities: list[dict[str, object]],
    ) -> RegistrationResult:
        response = await self._request(
            "POST",
            "api/v1/runners/register",
            {
                "enrollment_credential": enrollment_credential,
                "machine_fingerprint": machine_fingerprint,
                "agent_version": agent_version,
                "runtime_metadata": runtime_metadata,
                "capabilities": capabilities,
            },
            {"Idempotency-Key": _registration_idempotency_key(enrollment_credential)},
        )
        data = response["data"]
        return RegistrationResult(
            runner_id=data["runner"]["runner_id"],
            agent_token=data["agent_token"],
            token_version=data["token_version"],
        )

    async def heartbeat(
        self,
        runner_id: str,
        agent_token: str,
        agent_version: str,
        runtime_metadata: dict[str, object],
        capabilities: list[dict[str, object]],
        health_status: str = "HEALTHY",
    ) -> dict[str, object]:
        return await self._request(
            "POST",
            f"api/v1/runners/{runner_id}/heartbeat",
            {
                "health_status": health_status,
                "agent_version": agent_version,
                "runtime_metadata": runtime_metadata,
                "capabilities": capabilities,
            },
            {"X-Runner-Agent-Token": agent_token},
        )

    async def report_capabilities(
        self,
        runner_id: str,
        agent_token: str,
        capabilities: list[dict[str, object]],
    ) -> dict[str, object]:
        return await self._request(
            "POST",
            f"api/v1/runners/{runner_id}/capabilities",
            {"capabilities": capabilities},
            {"X-Runner-Agent-Token": agent_token},
        )

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, path, body, headers)

    def _request_sync(
        self,
        method: str,
        path: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        request = Request(
            urljoin(self._platform_url, path),
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            method=method,
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
        except HTTPError as error:
            code = "HTTP_ERROR"
            try:
                document = json.loads(error.read().decode("utf-8"))
                if isinstance(document.get("code"), str):
                    code = document["code"]
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            raise PlatformTransportError(error.code, code) from None
        except URLError:
            raise PlatformTransportError(None, "PLATFORM_UNREACHABLE") from None


def _registration_idempotency_key(enrollment_credential: str) -> str:
    digest = hashlib.sha256(enrollment_credential.encode("utf-8")).hexdigest()
    return f"runner-enrollment-{digest}"
