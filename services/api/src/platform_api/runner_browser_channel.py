"""Machine-authenticated direct command rendezvous for bound Runner browser work."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field

from platform_api.ai_exploration_schemas import AIExplorationBrowserAction
from platform_api.ai_exploration_service import (
    BoundBrowserCommand,
    BrowserActionResult,
    BrowserObservation,
)
from platform_api.errors import PlatformError
from platform_api.security import new_ulid


@dataclass(slots=True)
class _DirectExchange:
    command_id: str
    runner_id: str
    operation: str
    payload: dict[str, object] = field(repr=False)
    claimed: bool = False
    completed: bool = False
    response: dict[str, object] | None = None
    error_code: str | None = None


class RunnerBrowserCommandBroker:
    """One in-flight rendezvous per Runner; this is transport, never a scheduler queue."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._by_runner: dict[str, _DirectExchange] = {}
        self._cancel_by_runner: dict[str, _DirectExchange] = {}
        self._by_id: dict[str, _DirectExchange] = {}

    def dispatch(
        self,
        runner_id: str,
        operation: str,
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, object]:
        exchange = _DirectExchange(new_ulid(), runner_id, operation, payload)
        deadline = time.monotonic() + max(1, timeout_seconds)
        channel = self._cancel_by_runner if operation == "cancel" else self._by_runner
        with self._condition:
            if runner_id in channel:
                raise _runner_unavailable("The bound Runner already has an in-flight command.")
            channel[runner_id] = exchange
            self._by_id[exchange.command_id] = exchange
            self._condition.notify_all()
            try:
                while not exchange.completed:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise _runner_unavailable(
                            "The bound Runner did not complete the direct command before timeout."
                        )
                    self._condition.wait(remaining)
                if exchange.error_code is not None:
                    raise PlatformError(
                        title="Bound Runner command failed",
                        detail=(
                            "The machine-authenticated bound Runner rejected the browser command."
                        ),
                        status=409,
                        code=exchange.error_code,
                    )
                return dict(exchange.response or {})
            finally:
                if channel.get(runner_id) is exchange:
                    channel.pop(runner_id, None)
                self._by_id.pop(exchange.command_id, None)

    def claim(self, runner_id: str, timeout_seconds: int = 10) -> dict[str, object] | None:
        return self._claim(self._by_runner, runner_id, timeout_seconds)

    def claim_cancel(
        self, runner_id: str, timeout_seconds: int = 10
    ) -> dict[str, object] | None:
        """Claim the independent cancellation lane for an already bound Runner."""
        return self._claim(self._cancel_by_runner, runner_id, timeout_seconds)

    def _claim(
        self,
        channel: dict[str, _DirectExchange],
        runner_id: str,
        timeout_seconds: int,
    ) -> dict[str, object] | None:
        deadline = time.monotonic() + max(1, timeout_seconds)
        with self._condition:
            while True:
                exchange = channel.get(runner_id)
                if exchange is not None and not exchange.claimed:
                    exchange.claimed = True
                    return {
                        "command_id": exchange.command_id,
                        "runner_id": exchange.runner_id,
                        "operation": exchange.operation,
                        "payload": exchange.payload,
                    }
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)

    def complete(
        self,
        runner_id: str,
        command_id: str,
        response: dict[str, object] | None,
        error_code: str | None,
    ) -> None:
        with self._condition:
            exchange = self._by_id.get(command_id)
            if (
                exchange is None
                or exchange.runner_id != runner_id
                or not exchange.claimed
                or exchange.completed
            ):
                raise PlatformError(
                    title="Runner command conflict",
                    detail="The direct Runner command is no longer current.",
                    status=409,
                    code="AI_EXPLORATION_LEASE_LOST",
                )
            exchange.response = dict(response or {})
            exchange.error_code = error_code
            exchange.completed = True
            self._condition.notify_all()


class DirectRunnerBrowserRuntime:
    """API-side adapter that addresses exactly the Runner frozen in the Binding."""

    def __init__(self, broker: RunnerBrowserCommandBroker) -> None:
        self._broker = broker

    def start(self, command: BoundBrowserCommand) -> BrowserObservation:
        response = self._dispatch(command, "start", {})
        return _observation(response)

    def observe(
        self, command: BoundBrowserCommand, browser_session_id: str
    ) -> BrowserObservation:
        response = self._dispatch(
            command, "observe", {"browser_session_id": browser_session_id}
        )
        return _observation(response)

    def execute(
        self,
        command: BoundBrowserCommand,
        browser_session_id: str,
        action: AIExplorationBrowserAction,
    ) -> BrowserActionResult:
        response = self._dispatch(
            command,
            "execute",
            {
                "browser_session_id": browser_session_id,
                "action": action.model_dump(mode="json"),
            },
        )
        observation = _observation(response.get("observation"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise _runner_unavailable("The bound Runner returned an invalid action result.")
        return BrowserActionResult(result=result, observation=observation)

    def owns(self, command: BoundBrowserCommand, browser_session_id: str) -> bool:
        response = self._dispatch(command, "owns", {"browser_session_id": browser_session_id})
        return response.get("owned") is True

    def close(self, command: BoundBrowserCommand, browser_session_id: str) -> None:
        self._dispatch(command, "close", {"browser_session_id": browser_session_id})

    def cancel(
        self, command: BoundBrowserCommand, browser_session_id: str | None
    ) -> None:
        payload: dict[str, object] = {
            "bound_command": _serialize_command(command),
            "browser_session_id": browser_session_id,
        }
        self._broker.dispatch(
            command.runner_id,
            "cancel",
            payload,
            command.action_timeout_seconds * 2,
        )

    def _dispatch(
        self,
        command: BoundBrowserCommand,
        operation: str,
        body: dict[str, object],
    ) -> dict[str, object]:
        payload = {"bound_command": _serialize_command(command), **body}
        return self._broker.dispatch(
            command.runner_id,
            operation,
            payload,
            command.action_timeout_seconds,
        )


def _serialize_command(command: BoundBrowserCommand) -> dict[str, object]:
    return {
        "runner_id": command.runner_id,
        "execution_attempt_id": command.execution_attempt_id,
        "execution_binding_snapshot_id": command.execution_binding_snapshot_id,
        "identity_lease_generation": command.identity_lease_generation,
        "runner_lease_generation": command.runner_lease_generation,
        "target_url": command.target_url,
        "allowed_origins": list(command.allowed_origins),
        "authentication_redirect_origins": list(command.authentication_redirect_origins),
        "action_timeout_seconds": command.action_timeout_seconds,
        "login_material": {
            **asdict(command.login_material),
            "local_storage_presets": [
                asdict(item) for item in command.login_material.local_storage_presets
            ],
        },
    }


def _observation(value: object) -> BrowserObservation:
    if not isinstance(value, dict):
        raise _runner_unavailable("The bound Runner returned an invalid observation.")
    browser_session_id = value.get("browser_session_id")
    data = value.get("data")
    if not isinstance(browser_session_id, str) or not isinstance(data, dict):
        raise _runner_unavailable("The bound Runner returned an invalid observation.")
    return BrowserObservation(browser_session_id=browser_session_id, data=data)


def _runner_unavailable(detail: str) -> PlatformError:
    return PlatformError(
        title="Bound Runner unavailable",
        detail=detail,
        status=503,
        code="AI_EXPLORATION_RUNNER_UNAVAILABLE",
    )
