"""ModelGateway port and the real LiteLLM Proxy adapter."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol


@dataclass(frozen=True, slots=True)
class GatewayConnectionResult:
    status: str
    latency_ms: int
    provider_request_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class GatewayInvocationResult:
    status: str
    content: str | None
    provider_request_id: str | None
    message: str


class ModelGateway(Protocol):
    def test_connection(
        self,
        *,
        provider_code: str,
        model_name: str,
        provider_secret: str,
        timeout_seconds: int,
    ) -> GatewayConnectionResult: ...

    def invoke(
        self,
        *,
        provider_code: str,
        model_name: str,
        provider_secret: str,
        timeout_seconds: int,
        messages: list[dict[str, str]],
    ) -> GatewayInvocationResult: ...


class LiteLLMModelGateway:
    """Perform a minimal real completion through the deployment-owned LiteLLM Proxy."""

    _MAX_COMPLETION_TOKENS = 4096
    _MAX_RESPONSE_BYTES = 1_048_576

    _MODEL_PREFIXES: ClassVar[dict[str, str]] = {
        "OPENAI": "openai",
        "ANTHROPIC": "anthropic",
        "DEEPSEEK": "deepseek",
        "QWEN": "dashscope",
        "DOUBAO": "volcengine",
    }

    def __init__(
        self,
        proxy_url: str | None,
        proxy_api_key_file: Path | None = None,
        *,
        dynamic_credentials_enabled: bool = False,
    ) -> None:
        self._proxy_url = proxy_url.rstrip("/") if proxy_url else None
        self._proxy_api_key_file = proxy_api_key_file
        self._dynamic_credentials_enabled = dynamic_credentials_enabled

    def _proxy_api_key(self) -> str | None:
        if self._proxy_api_key_file is None:
            return None
        try:
            value = self._proxy_api_key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return value or None

    @staticmethod
    def _safe_request_id(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "".join(
            character
            for character in value.strip()
            if character.isascii() and (character.isalnum() or character in "-._:/")
        )
        return normalized[:191] or None

    @staticmethod
    def _result(
        status: str,
        started: float,
        message: str,
        provider_request_id: str | None = None,
    ) -> GatewayConnectionResult:
        return GatewayConnectionResult(
            status=status,
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            provider_request_id=provider_request_id,
            message=message,
        )

    def test_connection(
        self,
        *,
        provider_code: str,
        model_name: str,
        provider_secret: str,
        timeout_seconds: int,
    ) -> GatewayConnectionResult:
        started = time.monotonic()
        prefix = self._MODEL_PREFIXES.get(provider_code)
        if (
            self._proxy_url is None
            or prefix is None
            or not provider_secret
            or not self._dynamic_credentials_enabled
        ):
            return self._result(
                "INVALID_CONFIGURATION",
                started,
                "Secure client credential forwarding is not enabled for the model gateway.",
            )

        payload = json.dumps(
            {
                "model": f"{prefix}/{model_name}",
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "max_tokens": 2,
                "temperature": 0,
                "api_key": provider_secret,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        proxy_key = self._proxy_api_key()
        if self._proxy_api_key_file is not None and proxy_key is None:
            return self._result(
                "INVALID_CONFIGURATION",
                started,
                "The model gateway credential is unavailable.",
            )
        if proxy_key is not None:
            headers["Authorization"] = f"Bearer {proxy_key}"
        request = urllib.request.Request(
            f"{self._proxy_url}/v1/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                request_id = response.headers.get("x-request-id") or response.headers.get(
                    "x-litellm-request-id"
                )
                if 200 <= response.status < 300:
                    return self._result(
                        "SUCCESS",
                        started,
                        "The provider accepted a real gateway request.",
                        request_id,
                    )
                return self._result(
                    "PROVIDER_ERROR", started, "The model gateway returned an error."
                )
        except urllib.error.HTTPError as error:
            status = {
                401: "AUTHENTICATION_FAILED",
                403: "AUTHENTICATION_FAILED",
                404: "MODEL_NOT_FOUND",
                408: "TIMEOUT",
                429: "RATE_LIMITED",
            }.get(error.code, "PROVIDER_ERROR")
            request_id = error.headers.get("x-request-id") if error.headers else None
            error.close()
            return self._result(
                status,
                started,
                "The model gateway rejected the request.",
                request_id,
            )
        except TimeoutError:
            return self._result("TIMEOUT", started, "The model gateway request timed out.")
        except (urllib.error.URLError, OSError):
            return self._result(
                "PROVIDER_ERROR", started, "The model gateway could not be reached."
            )

    def invoke(
        self,
        *,
        provider_code: str,
        model_name: str,
        provider_secret: str,
        timeout_seconds: int,
        messages: list[dict[str, str]],
    ) -> GatewayInvocationResult:
        """Invoke one configured model through LiteLLM without logging credentials."""
        prefix = self._MODEL_PREFIXES.get(provider_code)
        if (
            self._proxy_url is None
            or prefix is None
            or not provider_secret
            or not self._dynamic_credentials_enabled
        ):
            return GatewayInvocationResult(
                status="INVALID_CONFIGURATION",
                content=None,
                provider_request_id=None,
                message="Secure client credential forwarding is not enabled for the model gateway.",
            )

        payload = json.dumps(
            {
                "model": f"{prefix}/{model_name}",
                "messages": messages,
                "temperature": 0,
                "max_tokens": self._MAX_COMPLETION_TOKENS,
                "response_format": {"type": "json_object"},
                "api_key": provider_secret,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        proxy_key = self._proxy_api_key()
        if self._proxy_api_key_file is not None and proxy_key is None:
            return GatewayInvocationResult(
                status="INVALID_CONFIGURATION",
                content=None,
                provider_request_id=None,
                message="The model gateway credential is unavailable.",
            )
        if proxy_key is not None:
            headers["Authorization"] = f"Bearer {proxy_key}"
        request = urllib.request.Request(
            f"{self._proxy_url}/v1/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                request_id = self._safe_request_id(
                    response.headers.get("x-request-id")
                    or response.headers.get("x-litellm-request-id")
                )
                if not 200 <= response.status < 300:
                    return GatewayInvocationResult(
                        status="PROVIDER_ERROR",
                        content=None,
                        provider_request_id=request_id,
                        message="The model gateway returned an error.",
                    )
                try:
                    raw_body = response.read(self._MAX_RESPONSE_BYTES + 1)
                    if len(raw_body) > self._MAX_RESPONSE_BYTES:
                        raise ValueError("completion response exceeds the bounded envelope")
                    body = json.loads(raw_body.decode("utf-8"))
                    content = body["choices"][0]["message"]["content"]
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    KeyError,
                    IndexError,
                    TypeError,
                    ValueError,
                ):
                    return GatewayInvocationResult(
                        status="INVALID_RESPONSE",
                        content=None,
                        provider_request_id=request_id,
                        message="The model gateway returned an invalid completion envelope.",
                    )
                if not isinstance(content, str) or not content.strip():
                    return GatewayInvocationResult(
                        status="INVALID_RESPONSE",
                        content=None,
                        provider_request_id=request_id,
                        message="The model gateway returned empty completion content.",
                    )
                return GatewayInvocationResult(
                    status="SUCCESS",
                    content=content,
                    provider_request_id=request_id,
                    message="The model gateway completed the request.",
                )
        except urllib.error.HTTPError as error:
            status = {
                401: "AUTHENTICATION_FAILED",
                403: "AUTHENTICATION_FAILED",
                404: "MODEL_NOT_FOUND",
                408: "TIMEOUT",
                429: "RATE_LIMITED",
            }.get(error.code, "PROVIDER_ERROR")
            request_id = self._safe_request_id(
                error.headers.get("x-request-id") if error.headers else None
            )
            error.close()
            return GatewayInvocationResult(
                status=status,
                content=None,
                provider_request_id=request_id,
                message="The model gateway rejected the request.",
            )
        except TimeoutError:
            return GatewayInvocationResult(
                status="TIMEOUT",
                content=None,
                provider_request_id=None,
                message="The model gateway request timed out.",
            )
        except (urllib.error.URLError, OSError):
            return GatewayInvocationResult(
                status="PROVIDER_ERROR",
                content=None,
                provider_request_id=None,
                message="The model gateway could not be reached.",
            )
