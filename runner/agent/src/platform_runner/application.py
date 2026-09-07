"""Runner Foundation runtime: registration, capability report, and heartbeat only."""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import os
import platform
import uuid
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import cast

from platform_runner.browser_runtime import (
    BrowserLoginMaterial,
    BrowserObservation,
    BrowserStoragePreset,
    DirectBrowserAction,
    DirectBrowserCommand,
    LoginMaterial,
    PlaywrightBoundBrowserRuntime,
)
from platform_runner.config import RunnerSettings
from platform_runner.credentials import AgentCredentialStore, StoredAgentIdentity
from platform_runner.transport import (
    HttpPlatformTransport,
    PlatformTransportError,
    RegistrationResult,
)

LOGGER = logging.getLogger(__name__)


class RunnerApplication:
    def __init__(
        self,
        settings: RunnerSettings,
        transport: HttpPlatformTransport | None = None,
        credential_store: AgentCredentialStore | None = None,
        capability_probe: Callable[[], Awaitable[list[dict[str, object]]]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.transport = transport or HttpPlatformTransport(str(settings.platform_url))
        self.credential_store = credential_store or AgentCredentialStore(
            settings.work_dir / "agent-identity.json"
        )
        self.capability_probe = capability_probe or self._capabilities
        self._sleep = sleep
        self.started = False
        self.identity: StoredAgentIdentity | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._browser_command_task: asyncio.Task[None] | None = None
        self._browser_cancel_task: asyncio.Task[None] | None = None
        self._browser_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")
        self._browser_runtime = PlaywrightBoundBrowserRuntime()

    async def start(self, *, runtime_enabled: bool = False) -> None:
        if self.started:
            raise RuntimeError("runner agent is already started")
        self.settings.work_dir.mkdir(parents=True, exist_ok=True)
        self.started = True
        LOGGER.info("runner agent started", extra={"service": self.settings.service_name})
        if not runtime_enabled:
            return
        capabilities = await self.capability_probe()
        self.identity = self.credential_store.load()
        if self.identity is None:
            enrollment = self.settings.enrollment_credential
            if enrollment is None:
                self.started = False
                raise RuntimeError(
                    "Runner enrollment credential or stored Agent identity is required"
                )
            registered = await self._register_with_retry(
                enrollment.get_secret_value(), capabilities
            )
            self.identity = StoredAgentIdentity(
                registered.runner_id, registered.agent_token, registered.token_version
            )
            self.credential_store.save(self.identity)
        await self.transport.report_capabilities(
            self.identity.runner_id, self.identity.agent_token, capabilities
        )
        await self.transport.heartbeat(
            self.identity.runner_id,
            self.identity.agent_token,
            self._agent_version(),
            self._runtime_metadata(),
            capabilities,
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if hasattr(self.transport, "claim_browser_command"):
            self._browser_command_task = asyncio.create_task(self._browser_command_loop())
        if hasattr(self.transport, "claim_browser_cancellation"):
            self._browser_cancel_task = asyncio.create_task(self._browser_cancel_loop())

    async def stop(self) -> None:
        if not self.started:
            return
        if self._heartbeat_task is not None:
            if not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._heartbeat_task
            self._heartbeat_task = None
        if self._browser_command_task is not None:
            if not self._browser_command_task.done():
                self._browser_command_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._browser_command_task
            self._browser_command_task = None
        if self._browser_cancel_task is not None:
            if not self._browser_cancel_task.done():
                self._browser_cancel_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._browser_cancel_task
            self._browser_cancel_task = None
        loop = asyncio.get_running_loop()
        with suppress(Exception):
            await loop.run_in_executor(self._browser_executor, self._browser_runtime.shutdown)
        self._browser_executor.shutdown(wait=False, cancel_futures=True)
        LOGGER.info("runner agent stopped", extra={"service": self.settings.service_name})
        self.started = False

    async def _heartbeat_loop(self) -> None:
        retry_delay = 1.0
        while True:
            await self._sleep(self.settings.heartbeat_interval_seconds)
            identity = self.identity
            if identity is None:
                raise RuntimeError("Runner Agent identity disappeared")
            capabilities = await self.capability_probe()
            try:
                await self.transport.heartbeat(
                    identity.runner_id,
                    identity.agent_token,
                    self._agent_version(),
                    self._runtime_metadata(),
                    capabilities,
                )
                retry_delay = 1.0
            except PlatformTransportError as error:
                if error.status in {401, 403}:
                    raise RuntimeError(
                        "Runner Agent authentication was rejected; import the current token"
                    ) from error
                LOGGER.warning(
                    "runner heartbeat failed; retrying",
                    extra={"status": error.status, "code": error.code},
                )
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def wait_for_runtime_failure(self) -> None:
        tasks = [
            task
            for task in (
                self._heartbeat_task,
                self._browser_command_task,
                self._browser_cancel_task,
            )
            if task is not None
        ]
        if not tasks:
            raise RuntimeError("Runner Agent heartbeat supervision is not active")
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await next(iter(done))
        raise RuntimeError("Runner Agent runtime task stopped unexpectedly")

    async def _browser_command_loop(self) -> None:
        identity = self.identity
        if identity is None:
            raise RuntimeError("Runner Agent identity is required for browser commands")
        retry_delay = 1.0
        while True:
            try:
                envelope = await self.transport.claim_browser_command(
                    identity.runner_id, identity.agent_token
                )
                retry_delay = 1.0
                if envelope is None:
                    await self._sleep(1.0)
                    continue
                await self._run_claimed_browser_command(identity, envelope)
            except PlatformTransportError as error:
                if error.status in {401, 403}:
                    raise RuntimeError(
                        "Runner Agent authentication was rejected for browser commands"
                    ) from error
                LOGGER.warning(
                    "runner browser command channel unavailable; retrying",
                    extra={"status": error.status, "code": error.code},
                )
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def _browser_cancel_loop(self) -> None:
        identity = self.identity
        if identity is None:
            raise RuntimeError("Runner Agent identity is required for browser cancellation")
        retry_delay = 1.0
        while True:
            try:
                envelope = await self.transport.claim_browser_cancellation(
                    identity.runner_id, identity.agent_token
                )
                retry_delay = 1.0
                if envelope is None:
                    await self._sleep(1.0)
                    continue
                await self._run_claimed_browser_command(identity, envelope)
            except PlatformTransportError as error:
                if error.status in {401, 403}:
                    raise RuntimeError(
                        "Runner Agent authentication was rejected for browser cancellation"
                    ) from error
                LOGGER.warning(
                    "runner browser cancellation channel unavailable; retrying",
                    extra={"status": error.status, "code": error.code},
                )
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def _run_claimed_browser_command(
        self, identity: StoredAgentIdentity, envelope: dict[str, object]
    ) -> None:
        loop = asyncio.get_running_loop()
        if envelope.get("operation") == "cancel":
            payload = cast(dict[str, object], envelope["payload"])
            raw_command = cast(dict[str, object], payload["bound_command"])
            if raw_command.get("runner_id") != identity.runner_id:
                raise PermissionError("command addressed to a different Runner")
            self._browser_runtime.request_cancel(_browser_command(raw_command))
        response, error_code = await loop.run_in_executor(
            self._browser_executor,
            self._execute_browser_command,
            identity.runner_id,
            envelope,
        )
        try:
            await self.transport.complete_browser_command(
                identity.runner_id,
                identity.agent_token,
                str(envelope.get("command_id", "")),
                response,
                error_code,
            )
        except PlatformTransportError as error:
            if error.status != 409 or envelope.get("operation") != "start" or not response:
                raise
            await loop.run_in_executor(
                self._browser_executor,
                self._close_rejected_start,
                identity.runner_id,
                envelope,
                response,
            )

    def _close_rejected_start(
        self,
        runner_id: str,
        envelope: dict[str, object],
        response: dict[str, object],
    ) -> None:
        """Close a session whose API rendezvous expired before start completed."""
        payload = cast(dict[str, object], envelope["payload"])
        raw_command = cast(dict[str, object], payload["bound_command"])
        if raw_command.get("runner_id") != runner_id:
            return
        browser_session_id = response.get("browser_session_id")
        if isinstance(browser_session_id, str) and browser_session_id:
            self._browser_runtime.close(_browser_command(raw_command), browser_session_id)

    def _execute_browser_command(
        self, runner_id: str, envelope: dict[str, object]
    ) -> tuple[dict[str, object] | None, str | None]:
        try:
            payload = cast(dict[str, object], envelope["payload"])
            raw_command = cast(dict[str, object], payload["bound_command"])
            if raw_command.get("runner_id") != runner_id:
                raise PermissionError("command addressed to a different Runner")
            command = _browser_command(raw_command)
            operation = envelope.get("operation")
            browser_session_id = str(payload.get("browser_session_id", ""))
            if operation == "start":
                return _observation_document(self._browser_runtime.start(command)), None
            if operation == "observe":
                return _observation_document(
                    self._browser_runtime.observe(command, browser_session_id)
                ), None
            if operation == "execute":
                raw_action = cast(dict[str, object], payload["action"])
                action = DirectBrowserAction(
                    type=str(raw_action["type"]),
                    selector=_optional_str(raw_action.get("selector")),
                    url=_optional_str(raw_action.get("url")),
                    value=_optional_str(raw_action.get("value")),
                    key=_optional_str(raw_action.get("key")),
                    direction=_optional_str(raw_action.get("direction")),
                    amount=(
                        int(cast(int | str, raw_action["amount"]))
                        if raw_action.get("amount") is not None
                        else None
                    ),
                )
                result = self._browser_runtime.execute(command, browser_session_id, action)
                return {
                    "result": result.result,
                    "observation": _observation_document(result.observation),
                }, None
            if operation == "owns":
                return {"owned": self._browser_runtime.owns(command, browser_session_id)}, None
            if operation == "close":
                self._browser_runtime.close(command, browser_session_id)
                return {"closed": True}, None
            if operation == "cancel":
                self._browser_runtime.cancel(
                    command,
                    browser_session_id if browser_session_id else None,
                )
                return {"cancelled": True}, None
            raise ValueError("unsupported direct browser operation")
        except PermissionError:
            return None, "AI_EXPLORATION_LEASE_LOST"
        except Exception:
            return None, "AI_EXPLORATION_ACTION_FAILED"

    async def _register_with_retry(
        self, enrollment_credential: str, capabilities: list[dict[str, object]]
    ) -> RegistrationResult:
        retry_delay = 1.0
        while True:
            try:
                return await self.transport.register(
                    enrollment_credential,
                    self._machine_fingerprint(),
                    self._agent_version(),
                    self._runtime_metadata(),
                    capabilities,
                )
            except PlatformTransportError as error:
                if error.status is not None and error.status < 500:
                    raise
                LOGGER.warning(
                    "runner registration delivery failed; retrying idempotently",
                    extra={"status": error.status, "code": error.code},
                )
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)

    async def _capabilities(self) -> list[dict[str, object]]:
        capabilities: dict[str, dict[str, object]] = {
            "AGENT_VERSION": {
                "capability_code": "AGENT_VERSION",
                "availability_status": "CONFIGURED",
                "observed_version": self._agent_version(),
                "observed_metadata": None,
            },
            "PLAYWRIGHT_VERSION": {
                "capability_code": "PLAYWRIGHT_VERSION",
                "availability_status": "CONFIGURED",
                "observed_version": _package_version("playwright"),
                "observed_metadata": None,
            },
        }
        for code in self.settings.declared_capabilities:
            capabilities[code] = {
                "capability_code": code,
                "availability_status": "CONFIGURED",
                "observed_version": None,
                "observed_metadata": None,
            }
        return list(capabilities.values())

    @staticmethod
    def _agent_version() -> str:
        return _package_version("platform-runner")

    @staticmethod
    def _machine_fingerprint() -> str:
        material = f"{platform.system()}|{platform.machine()}|{platform.node()}|{uuid.getnode()}"
        return material

    @staticmethod
    def _runtime_metadata() -> dict[str, object]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "process_id": os.getpid(),
        }


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _browser_command(value: dict[str, object]) -> DirectBrowserCommand:
    material = cast(dict[str, object], value["login_material"])
    presets = tuple(
        BrowserStoragePreset(
            key=str(cast(dict[str, object], item)["key"]),
            value=str(cast(dict[str, object], item)["value"]),
            set_before_login=bool(cast(dict[str, object], item)["set_before_login"]),
        )
        for item in cast(list[object], material.get("local_storage_presets", []))
    )
    return DirectBrowserCommand(
        runner_id=str(value["runner_id"]),
        execution_attempt_id=str(value["execution_attempt_id"]),
        execution_binding_snapshot_id=str(value["execution_binding_snapshot_id"]),
        identity_lease_generation=int(cast(int, value["identity_lease_generation"])),
        runner_lease_generation=int(cast(int, value["runner_lease_generation"])),
        target_url=str(value["target_url"]),
        allowed_origins=tuple(str(item) for item in cast(list[object], value["allowed_origins"])),
        authentication_redirect_origins=tuple(
            str(item)
            for item in cast(list[object], value["authentication_redirect_origins"])
        ),
        action_timeout_seconds=int(cast(int, value["action_timeout_seconds"])),
        login_material=cast(
            LoginMaterial,
            BrowserLoginMaterial(
                account_identifier=str(material["account_identifier"]),
                secret_value=str(material["secret_value"]),
                login_url=_optional_str(material.get("login_url")),
                local_storage_presets=presets,
                refresh_after_local_storage=bool(material.get("refresh_after_local_storage")),
                captcha_policy=str(material.get("captcha_policy", "NONE")),
                captcha_request_header_name=_optional_str(
                    material.get("captcha_request_header_name")
                ),
                captcha_request_header_value=_optional_str(
                    material.get("captcha_request_header_value")
                ),
                captcha_response_header_name=_optional_str(
                    material.get("captcha_response_header_name")
                ),
            ),
        ),
    )


def _observation_document(observation: BrowserObservation) -> dict[str, object]:
    return {
        "browser_session_id": str(observation.browser_session_id),
        "data": observation.data,
    }


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
