import asyncio
import hashlib
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from platform_runner import RunnerApplication, RunnerSettings
from platform_runner.adapters import ArtifactCollector, BrowserAdapter, PlatformTransport
from platform_runner.browser_runtime import PlaywrightBoundBrowserRuntime
from platform_runner.credentials import AgentCredentialStore, StoredAgentIdentity
from platform_runner.transport import (
    HttpPlatformTransport,
    PlatformTransportError,
    RegistrationResult,
)


class FakeBrowserAdapter:
    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None


class FakePlatformTransport:
    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None


class FakeArtifactCollector:
    async def collect(self, source: Path) -> Path:
        return source


def test_runner_starts_and_stops_without_platform_business_actions() -> None:
    async def scenario() -> None:
        settings = RunnerSettings(
            _env_file=None,
            environment="test",
            platform_url="http://127.0.0.1:8000",
            work_dir=Path(".runtime/runner-test"),
        )
        application = RunnerApplication(settings)

        await application.start()
        assert application.started is True
        await application.stop()
        assert application.started is False

    asyncio.run(scenario())


def test_runner_adapter_protocols_are_replaceable() -> None:
    assert isinstance(FakeBrowserAdapter(), BrowserAdapter)
    assert isinstance(FakePlatformTransport(), PlatformTransport)
    assert isinstance(FakeArtifactCollector(), ArtifactCollector)


class MemoryCredentialStore:
    def __init__(self, identity: StoredAgentIdentity | None = None) -> None:
        self.identity = identity
        self.saved: list[StoredAgentIdentity] = []

    def load(self) -> StoredAgentIdentity | None:
        return self.identity

    def save(self, identity: StoredAgentIdentity) -> None:
        self.identity = identity
        self.saved.append(identity)


class RecordingRunnerTransport:
    def __init__(self) -> None:
        self.register_calls: list[dict[str, object]] = []
        self.capability_calls: list[tuple[str, str, list[dict[str, object]]]] = []
        self.heartbeat_calls: list[tuple[str, str, list[dict[str, object]]]] = []

    async def register(
        self,
        enrollment_credential: str,
        machine_fingerprint: str,
        agent_version: str,
        runtime_metadata: dict[str, object],
        capabilities: list[dict[str, object]],
    ) -> RegistrationResult:
        self.register_calls.append(
            {
                "enrollment_credential": enrollment_credential,
                "machine_fingerprint": machine_fingerprint,
                "agent_version": agent_version,
                "runtime_metadata": runtime_metadata,
                "capabilities": capabilities,
            }
        )
        return RegistrationResult("R" * 26, "rat_" + "t" * 48, 1)

    async def report_capabilities(
        self,
        runner_id: str,
        agent_token: str,
        capabilities: list[dict[str, object]],
    ) -> dict[str, object]:
        self.capability_calls.append((runner_id, agent_token, capabilities))
        return {}

    async def heartbeat(
        self,
        runner_id: str,
        agent_token: str,
        agent_version: str,
        runtime_metadata: dict[str, object],
        capabilities: list[dict[str, object]],
        health_status: str = "HEALTHY",
    ) -> dict[str, object]:
        del agent_version, runtime_metadata, health_status
        self.heartbeat_calls.append((runner_id, agent_token, capabilities))
        return {}


def _runtime_settings(tmp_path: Path, *, enrollment: str | None = None) -> RunnerSettings:
    return RunnerSettings(
        _env_file=None,
        environment="test",
        platform_url="http://127.0.0.1:8000",
        work_dir=tmp_path,
        enrollment_credential=enrollment,
        heartbeat_interval_seconds=300,
        declared_capabilities=["BROWSER_CHROMIUM"],
    )


def test_runtime_registers_once_then_uses_agent_identity_for_machine_calls(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        transport = RecordingRunnerTransport()
        store = MemoryCredentialStore()
        app = RunnerApplication(
            _runtime_settings(tmp_path, enrollment="enr_" + "e" * 48),
            transport=transport,  # type: ignore[arg-type]
            credential_store=store,  # type: ignore[arg-type]
        )

        await app.start(runtime_enabled=True)
        try:
            assert len(transport.register_calls) == 1
            assert transport.register_calls[0]["enrollment_credential"] == "enr_" + "e" * 48
            assert store.saved == [StoredAgentIdentity("R" * 26, "rat_" + "t" * 48, 1)]
            assert transport.capability_calls[0][0:2] == ("R" * 26, "rat_" + "t" * 48)
            assert transport.heartbeat_calls[0][0:2] == ("R" * 26, "rat_" + "t" * 48)
            codes = {item["capability_code"] for item in transport.capability_calls[0][2]}
            assert {"AGENT_VERSION", "PLAYWRIGHT_VERSION", "BROWSER_CHROMIUM"} <= codes
        finally:
            await app.stop()

    asyncio.run(scenario())


def test_runtime_reuses_stored_agent_token_without_enrollment(tmp_path: Path) -> None:
    async def scenario() -> None:
        transport = RecordingRunnerTransport()
        identity = StoredAgentIdentity("R" * 26, "rat_" + "s" * 48, 3)
        store = MemoryCredentialStore(identity)
        app = RunnerApplication(
            _runtime_settings(tmp_path),
            transport=transport,  # type: ignore[arg-type]
            credential_store=store,  # type: ignore[arg-type]
        )

        await app.start(runtime_enabled=True)
        try:
            assert transport.register_calls == []
            assert transport.capability_calls[0][0:2] == (identity.runner_id, identity.agent_token)
            assert transport.heartbeat_calls[0][0:2] == (identity.runner_id, identity.agent_token)
        finally:
            await app.stop()

    asyncio.run(scenario())


def test_fresh_enrollment_and_restart_authenticate_with_protected_identity(
    tmp_path: Path,
) -> None:
    runner_id = "R" * 26
    agent_token = "rat_" + "p" * 43
    token_hash = hashlib.sha256(agent_token.encode("utf-8")).digest()
    calls = {"register": 0, "capabilities": 0, "heartbeat": 0}

    class MachineAuthHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(content_length)
            status = 200
            response: dict[str, object] = {"data": None}
            if self.path.endswith("/register"):
                calls["register"] += 1
                response = {
                    "data": {
                        "runner": {"runner_id": runner_id},
                        "agent_token": agent_token,
                        "token_version": 1,
                    }
                }
            else:
                supplied = self.headers.get("X-Runner-Agent-Token", "")
                if not secrets.compare_digest(
                    hashlib.sha256(supplied.encode("utf-8")).digest(), token_hash
                ):
                    status = 401
                    response = {"code": "RUNNER_AGENT_UNAUTHENTICATED"}
                elif self.path.endswith("/capabilities"):
                    calls["capabilities"] += 1
                    response = {"data": {}}
                elif self.path.endswith("/heartbeat"):
                    calls["heartbeat"] += 1
                    response = {"data": {}}
            payload = json.dumps(response).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), MachineAuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def scenario() -> None:
        identity_path = tmp_path / "agent-identity.json"
        first = RunnerApplication(
            RunnerSettings(
                _env_file=None,
                environment="test",
                platform_url=f"http://127.0.0.1:{server.server_port}",
                work_dir=tmp_path,
                enrollment_credential="enr_" + "e" * 48,
                heartbeat_interval_seconds=300,
                declared_capabilities=["BROWSER_CHROMIUM"],
            )
        )
        await first.start(runtime_enabled=True)
        await first.stop()

        envelope = json.loads(identity_path.read_text(encoding="utf-8"))
        assert set(envelope) == {"format", "protected"}
        assert agent_token not in identity_path.read_text(encoding="utf-8")
        assert calls == {"register": 1, "capabilities": 1, "heartbeat": 1}

        restarted = RunnerApplication(
            RunnerSettings(
                _env_file=None,
                environment="test",
                platform_url=f"http://127.0.0.1:{server.server_port}",
                work_dir=tmp_path,
                heartbeat_interval_seconds=300,
                declared_capabilities=["BROWSER_CHROMIUM"],
            )
        )
        await restarted.start(runtime_enabled=True)
        await restarted.stop()

        assert calls == {"register": 1, "capabilities": 2, "heartbeat": 2}

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class HeaderCaptureTransport(HttpPlatformTransport):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:8000")
        self.requests: list[tuple[str, str, dict[str, object], dict[str, str]]] = []

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        self.requests.append((method, path, body, headers))
        if path.endswith("/register"):
            return {
                "data": {
                    "runner": {"runner_id": "R" * 26},
                    "agent_token": "rat_" + "a" * 48,
                    "token_version": 1,
                }
            }
        return {}


def test_transport_never_uses_human_bearer_for_machine_interfaces() -> None:
    async def scenario() -> None:
        transport = HeaderCaptureTransport()
        registration = await transport.register("enr_" + "e" * 48, "machine", "1.0.0", {}, [])
        await transport.report_capabilities(registration.runner_id, registration.agent_token, [])
        await transport.heartbeat(registration.runner_id, registration.agent_token, "1.0.0", {}, [])

        assert "Authorization" not in transport.requests[0][3]
        assert set(transport.requests[0][3]) == {"Idempotency-Key"}
        first_key = transport.requests[0][3]["Idempotency-Key"]
        await transport.register("enr_" + "e" * 48, "machine", "1.0.0", {}, [])
        assert transport.requests[-1][3]["Idempotency-Key"] == first_key
        for _, _, _, headers in transport.requests[1:]:
            if "X-Runner-Agent-Token" in headers:
                assert headers == {"X-Runner-Agent-Token": registration.agent_token}

    asyncio.run(scenario())


def test_transport_maps_long_poll_timeout_to_transient_unreachable() -> None:
    transport = HttpPlatformTransport("http://127.0.0.1:8000")

    with patch("platform_runner.transport.urlopen", side_effect=TimeoutError("timed out")):
        try:
            transport._request_sync("POST", "claim", {}, {}, timeout_seconds=15.0)
        except PlatformTransportError as error:
            assert error.status is None
            assert error.code == "PLATFORM_UNREACHABLE"
        else:
            raise AssertionError("long-poll timeout escaped the transient transport boundary")


def test_agent_token_is_protected_at_rest(tmp_path: Path) -> None:
    token = "rat_" + "z" * 48
    store = AgentCredentialStore(tmp_path / "agent-identity.json")
    identity = StoredAgentIdentity("R" * 26, token, 2)

    store.save(identity)

    assert token not in (tmp_path / "agent-identity.json").read_text(encoding="utf-8")
    assert store.load() == identity


def test_registration_retries_transient_delivery_failure_with_same_request(tmp_path: Path) -> None:
    class FlakyRegistrationTransport(RecordingRunnerTransport):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        async def register(self, *args: object, **kwargs: object) -> RegistrationResult:
            self.attempts += 1
            if self.attempts == 1:
                raise PlatformTransportError(None, "PLATFORM_UNREACHABLE")
            return await super().register(*args, **kwargs)  # type: ignore[arg-type]

    async def scenario() -> None:
        transport = FlakyRegistrationTransport()
        sleeps: list[float] = []

        async def no_wait(delay: float) -> None:
            sleeps.append(delay)

        app = RunnerApplication(
            _runtime_settings(tmp_path, enrollment="enr_" + "e" * 48),
            transport=transport,  # type: ignore[arg-type]
            credential_store=MemoryCredentialStore(),  # type: ignore[arg-type]
            sleep=no_wait,
        )
        await app.start(runtime_enabled=True)
        try:
            assert transport.attempts == 2
            assert sleeps[0] == 1.0
        finally:
            await app.stop()

    asyncio.run(scenario())


def test_heartbeat_authentication_failure_reaches_cli_supervisor(tmp_path: Path) -> None:
    class RevokedTransport(RecordingRunnerTransport):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        async def heartbeat(self, *args: object, **kwargs: object) -> dict[str, object]:
            self.attempts += 1
            if self.attempts > 1:
                raise PlatformTransportError(401, "RUNNER_AGENT_UNAUTHENTICATED")
            return await super().heartbeat(*args, **kwargs)  # type: ignore[arg-type]

    async def scenario() -> None:
        transport = RevokedTransport()

        async def no_wait(_: float) -> None:
            return None

        app = RunnerApplication(
            _runtime_settings(tmp_path),
            transport=transport,  # type: ignore[arg-type]
            credential_store=MemoryCredentialStore(
                StoredAgentIdentity("R" * 26, "rat_" + "s" * 48, 3)
            ),  # type: ignore[arg-type]
            sleep=no_wait,
        )
        await app.start(runtime_enabled=True)
        try:
            try:
                await app.wait_for_runtime_failure()
            except RuntimeError as error:
                assert "authentication was rejected" in str(error)
            else:
                raise AssertionError("heartbeat authentication failure was swallowed")
        finally:
            await app.stop()

    asyncio.run(scenario())


def test_bound_browser_runtime_executes_typed_action_and_denies_foreign_origin() -> None:
    foreign_requests: list[str] = []

    class ForeignHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            foreign_requests.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            return None

    foreign_server = ThreadingHTTPServer(("127.0.0.1", 0), ForeignHandler)
    foreign_thread = threading.Thread(target=foreign_server.serve_forever, daemon=True)
    foreign_thread.start()
    foreign_origin = f"http://127.0.0.1:{foreign_server.server_port}"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/dashboard":
                body = (
                    "<html><title>Dashboard</title><body>Goal reached"
                    f"<a data-testid='foreign' href='{foreign_origin}/leak'>Foreign</a>"
                    "</body></html>"
                ).encode()
            else:
                body = (
                    b"<html><title>Login</title><body>"
                    b"<p>fixture-password</p>"
                    b"<a data-testid='continue' href='/dashboard'>Continue</a>"
                    b"</body></html>"
                )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    command = SimpleNamespace(
        runner_id="R" * 26,
        execution_attempt_id="A" * 26,
        execution_binding_snapshot_id="B" * 26,
        identity_lease_generation=3,
        runner_lease_generation=7,
        target_url=f"{origin}/login",
        allowed_origins=(origin,),
        authentication_redirect_origins=(),
        action_timeout_seconds=5,
        login_material=SimpleNamespace(
            account_identifier="fixture-user",
            secret_value="fixture-password",
            login_url=None,
            local_storage_presets=(),
            refresh_after_local_storage=False,
            captcha_policy="NONE",
            captcha_request_header_name=None,
            captcha_request_header_value=None,
            captcha_response_header_name=None,
        ),
    )
    runtime = PlaywrightBoundBrowserRuntime()
    observation = runtime.start(command)
    try:
        assert observation.data["title"] == "Login"
        assert "fixture-password" not in repr(observation.data)
        assert "[REDACTED]" in repr(observation.data)
        assert runtime.owns(command, observation.browser_session_id)
        result = runtime.execute(
            command,
            observation.browser_session_id,
            SimpleNamespace(type="Click", selector="testid=continue"),
        )
        assert result.result["status"] == "SUCCEEDED"
        assert result.observation.data["title"] == "Dashboard"
        try:
            runtime.execute(
                command,
                observation.browser_session_id,
                SimpleNamespace(type="Click", selector="testid=foreign"),
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("foreign navigation origin was accepted")
        assert foreign_requests == []
        runtime.cancel(command, None)
        assert not runtime.owns(command, observation.browser_session_id)
    finally:
        runtime.close(command, observation.browser_session_id)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        foreign_server.shutdown()
        foreign_server.server_close()
        foreign_thread.join(timeout=5)


def test_late_start_completion_is_closed_when_api_rendezvous_expired(tmp_path: Path) -> None:
    closed: list[tuple[str, str]] = []

    class ClosingRuntime:
        def close(self, command: object, browser_session_id: str) -> None:
            closed.append((str(cast(Any, command).runner_id), browser_session_id))

    app = RunnerApplication(_runtime_settings(tmp_path))
    app._browser_runtime = ClosingRuntime()  # type: ignore[assignment]
    envelope: dict[str, object] = {
        "operation": "start",
        "payload": {
            "bound_command": {
                "runner_id": "R" * 26,
                "execution_attempt_id": "A" * 26,
                "execution_binding_snapshot_id": "B" * 26,
                "identity_lease_generation": 3,
                "runner_lease_generation": 7,
                "target_url": "https://example.test",
                "allowed_origins": ["https://example.test"],
                "authentication_redirect_origins": [],
                "action_timeout_seconds": 5,
                "login_material": {
                    "account_identifier": "fixture-user",
                    "secret_value": "fixture-password",
                    "login_url": None,
                    "local_storage_presets": [],
                    "refresh_after_local_storage": False,
                    "captcha_policy": "NONE",
                    "captcha_request_header_name": None,
                    "captcha_request_header_value": None,
                    "captcha_response_header_name": None,
                },
            }
        },
    }
    app._close_rejected_start(
        "R" * 26,
        envelope,
        {"browser_session_id": "browser-session-late", "data": {}},
    )
    app._browser_executor.shutdown(wait=False, cancel_futures=True)
    assert closed == [("R" * 26, "browser-session-late")]


def test_bound_browser_runtime_requires_observable_login_success_and_keeps_secrets_out() -> None:
    requests: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def _login_page(self) -> bytes:
            return (
                b"<html><title>Login</title><body>"
                b"<form method='post' action='/login'>"
                b"<input name='username' autocomplete='username'>"
                b"<input type='password' name='password'>"
                b"<input name='captcha' autocomplete='one-time-code'>"
                b"<button type='submit'>Sign in</button></form></body></html>"
            )

        def do_GET(self) -> None:
            requests.append(("GET", self.path))
            if self.path == "/login":
                body = self._login_page()
                self.send_response(200)
                self.send_header("x-captcha-code", "2468")
            elif self.path.startswith("/dashboard"):
                body = b"<html><title>Dashboard</title><body>Authenticated home</body></html>"
                self.send_response(200)
            else:
                body = b"not found"
                self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            requests.append(("POST", self.path))
            if (
                self.path == "/login"
                and "fixture-user" in body
                and "fixture-password" in body
                and "2468" in body
                and self.headers.get("Show-Captcha-Code") == "true"
            ):
                self.send_response(302)
                self.send_header("Location", "/dashboard?session_secret=must-not-persist")
                self.end_headers()
                return
            response = self._login_page()
            self.send_response(401)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    command = SimpleNamespace(
        runner_id="R" * 26,
        execution_attempt_id="A" * 26,
        execution_binding_snapshot_id="B" * 26,
        identity_lease_generation=3,
        runner_lease_generation=7,
        target_url=f"{origin}/dashboard",
        allowed_origins=(origin,),
        authentication_redirect_origins=(),
        action_timeout_seconds=5,
        login_material=SimpleNamespace(
            account_identifier="fixture-user",
            secret_value="fixture-password",
            login_url=f"{origin}/login",
            local_storage_presets=(),
            refresh_after_local_storage=False,
            captcha_policy="RESPONSE_HEADER",
            captcha_request_header_name="Show-Captcha-Code",
            captcha_request_header_value="true",
            captcha_response_header_name="x-captcha-code",
        ),
    )
    runtime = PlaywrightBoundBrowserRuntime()
    try:
        observation = runtime.start(command)
        assert observation.data["title"] == "Dashboard"
        assert observation.data["current_url"] == f"{origin}/dashboard"
        assert observation.data["login_state_marker"] == {
            "status": "SUCCEEDED",
            "signal": "AUTHENTICATED_URL",
            "login_submitted": True,
        }
        rendered = repr(observation.data)
        for secret in ("fixture-user", "fixture-password", "2468", "must-not-persist"):
            assert secret not in rendered
        assert ("POST", "/login") in requests
    finally:
        for session_id in tuple(runtime._sessions):
            runtime.close(command, session_id)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_bound_browser_runtime_rejects_failed_login_before_target_navigation() -> None:
    target_requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        @staticmethod
        def _login_page() -> bytes:
            return (
                b"<html><title>Login</title><body><form method='post' action='/login'>"
                b"<input name='username'><input type='password' name='password'>"
                b"<button type='submit'>Sign in</button></form></body></html>"
            )

        def do_GET(self) -> None:
            if self.path.startswith("/dashboard"):
                target_requests.append(self.path)
                body = b"<html><title>Dashboard</title></html>"
            else:
                body = self._login_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = self._login_page()
            self.send_response(401)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    command = SimpleNamespace(
        runner_id="R" * 26,
        execution_attempt_id="A" * 26,
        execution_binding_snapshot_id="B" * 26,
        identity_lease_generation=3,
        runner_lease_generation=7,
        target_url=f"{origin}/dashboard",
        allowed_origins=(origin,),
        authentication_redirect_origins=(),
        action_timeout_seconds=1,
        login_material=SimpleNamespace(
            account_identifier="fixture-user",
            secret_value="fixture-password",
            login_url=f"{origin}/login",
            local_storage_presets=(),
            refresh_after_local_storage=False,
            captcha_policy="NONE",
            captcha_request_header_name=None,
            captcha_request_header_value=None,
            captcha_response_header_name=None,
        ),
    )
    runtime = PlaywrightBoundBrowserRuntime()
    try:
        try:
            runtime.start(command)
        except RuntimeError as error:
            assert "observable login success signal was not observed" in str(error)
        else:
            raise AssertionError("failed login was accepted")
        assert target_requests == []
        assert runtime._sessions == {}
    finally:
        runtime.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_bound_browser_runtime_stops_playwright_when_chromium_launch_fails() -> None:
    stopped: list[bool] = []

    class Chromium:
        def launch(self, **_kwargs: object) -> object:
            raise RuntimeError("chromium unavailable")

    class FakePlaywright:
        chromium = Chromium()

        def stop(self) -> None:
            stopped.append(True)

    class Starter:
        def start(self) -> FakePlaywright:
            return FakePlaywright()

    command = SimpleNamespace(
        runner_id="R" * 26,
        execution_attempt_id="A" * 26,
        execution_binding_snapshot_id="B" * 26,
        identity_lease_generation=3,
        runner_lease_generation=7,
        target_url="https://example.test",
        allowed_origins=("https://example.test",),
        authentication_redirect_origins=(),
        action_timeout_seconds=1,
        login_material=SimpleNamespace(
            account_identifier="fixture-user",
            secret_value="fixture-password",
            login_url=None,
            local_storage_presets=(),
            refresh_after_local_storage=False,
            captcha_policy="NONE",
            captcha_request_header_name=None,
            captcha_request_header_value=None,
            captcha_response_header_name=None,
        ),
    )
    runtime = PlaywrightBoundBrowserRuntime()
    with patch("platform_runner.browser_runtime.sync_playwright", return_value=Starter()):
        try:
            runtime.start(command)
        except RuntimeError as error:
            assert "chromium unavailable" in str(error)
        else:
            raise AssertionError("chromium launch failure was swallowed")
    assert stopped == [True]
    assert runtime._playwright is None
    assert runtime._browser is None
