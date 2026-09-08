"""Bound-direct Playwright runtime for the closed AI exploration action DSL."""

from __future__ import annotations

import re
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    Route,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)


@dataclass(frozen=True, slots=True)
class BrowserObservation:
    browser_session_id: str
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class BrowserActionResult:
    result: dict[str, object]
    observation: BrowserObservation


class BoundBrowserCommand(Protocol):
    runner_id: str
    execution_attempt_id: str
    execution_binding_snapshot_id: str
    identity_lease_generation: int
    runner_lease_generation: int
    target_url: str
    allowed_origins: tuple[str, ...]
    authentication_redirect_origins: tuple[str, ...]
    action_timeout_seconds: int
    login_material: LoginMaterial


class StoragePreset(Protocol):
    key: str
    value: str
    set_before_login: bool


class LoginMaterial(Protocol):
    account_identifier: str
    secret_value: str
    login_url: str | None
    local_storage_presets: tuple[StoragePreset, ...]
    refresh_after_local_storage: bool
    captcha_policy: str
    captcha_request_header_name: str | None
    captcha_request_header_value: str | None
    captcha_response_header_name: str | None


class BrowserAction(Protocol):
    type: str
    selector: str | None
    url: object | None
    value: str | None
    key: str | None
    direction: str | None
    amount: int | None


@dataclass(slots=True)
class BrowserStoragePreset:
    key: str
    value: str
    set_before_login: bool


@dataclass(slots=True)
class BrowserLoginMaterial:
    account_identifier: str
    secret_value: str = field(repr=False)
    login_url: str | None = None
    local_storage_presets: tuple[BrowserStoragePreset, ...] = ()
    refresh_after_local_storage: bool = False
    captcha_policy: str = "NONE"
    captcha_request_header_name: str | None = None
    captcha_request_header_value: str | None = field(default=None, repr=False)
    captcha_response_header_name: str | None = None


@dataclass(slots=True)
class DirectBrowserCommand:
    runner_id: str
    execution_attempt_id: str
    execution_binding_snapshot_id: str
    identity_lease_generation: int
    runner_lease_generation: int
    target_url: str
    allowed_origins: tuple[str, ...]
    authentication_redirect_origins: tuple[str, ...]
    action_timeout_seconds: int
    login_material: LoginMaterial = field(repr=False)


@dataclass(slots=True)
class DirectBrowserAction:
    type: str
    selector: str | None = None
    url: object | None = None
    value: str | None = None
    key: str | None = None
    direction: str | None = None
    amount: int | None = None


@dataclass(slots=True)
class _Session:
    context: BrowserContext
    page: Page
    command_identity: tuple[str, str, str, int, int]
    allowed_origins: frozenset[str]
    navigation_violation: str | None = None
    previous_action_result: dict[str, object] | None = None
    captcha_value: str | None = field(default=None, repr=False)
    login_state_marker: dict[str, object] | None = None


class PlaywrightBoundBrowserRuntime:
    """Execute only commands addressed to the frozen Runner/Attempt/Binding identity."""

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._sessions: dict[str, _Session] = {}
        self._cancel_lock = threading.Lock()
        self._cancelled_identities: set[tuple[str, str, str, int, int]] = set()

    def start(self, command: BoundBrowserCommand) -> BrowserObservation:
        self._raise_if_cancelled(command)
        target_url = str(command.target_url)
        allowed = self._allowed_origins(command)
        self._require_allowed(target_url, allowed)
        self._ensure_browser()
        assert self._browser is not None
        context: BrowserContext | None = None
        session_id: str | None = None
        try:
            context = self._browser.new_context()
            page = context.new_page()
            session_id = uuid.uuid4().hex
            session = _Session(
                context=context,
                page=page,
                command_identity=self._command_identity(command),
                allowed_origins=allowed,
            )
            self._sessions[session_id] = session
            context.route("**/*", lambda route: self._route_navigation(session, route))
            context.on("page", lambda candidate: self._watch_page(session, candidate))
            self._watch_page(session, page)
            self._configure_captcha_capture(session, command)
            login_url = command.login_material.login_url or target_url
            self._require_allowed(login_url, allowed)
            page.goto(login_url, wait_until="domcontentloaded", timeout=self._timeout_ms(command))
            self._raise_if_cancelled(command)
            self._apply_storage(session, command, before_login=True)
            self._perform_login(session, command)
            self._raise_if_cancelled(command)
            self._apply_storage(session, command, before_login=False)
            if command.login_material.login_url and page.url != target_url:
                page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=self._timeout_ms(command),
                )
            self._raise_if_cancelled(command)
            self._validate_pages(session)
            return self._observe(session_id, session, command)
        except Exception:
            if session_id is not None and session_id in self._sessions:
                with suppress(Exception):
                    self.close(command, session_id)
            else:
                if context is not None:
                    with suppress(Exception):
                        context.close()
                self._shutdown_if_idle()
            raise

    def observe(self, command: BoundBrowserCommand, browser_session_id: str) -> BrowserObservation:
        self._raise_if_cancelled(command)
        session = self._session(command, browser_session_id)
        self._raise_if_cancelled(command)
        self._validate_pages(session)
        return self._observe(browser_session_id, session, command)

    def execute(
        self,
        command: BoundBrowserCommand,
        browser_session_id: str,
        action: BrowserAction,
    ) -> BrowserActionResult:
        session = self._session(command, browser_session_id)
        page = session.page
        action_type = str(action.type)
        timeout = self._timeout_ms(command)
        result: dict[str, object] = {"status": "SUCCEEDED", "action": action_type}
        if action_type == "Navigate":
            url = str(action.url)
            self._require_allowed(url, session.allowed_origins)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        elif action_type in {
            "Click",
            "Fill",
            "Select",
            "Check",
            "Uncheck",
            "WaitFor",
            "Inspect",
            "Read",
        }:
            locator = self._locator(page, str(action.selector))
            if action_type == "Click":
                locator.click(timeout=timeout)
            elif action_type == "Fill":
                locator.fill(str(action.value), timeout=timeout)
            elif action_type == "Select":
                locator.select_option(str(action.value), timeout=timeout)
            elif action_type == "Check":
                locator.check(timeout=timeout)
            elif action_type == "Uncheck":
                locator.uncheck(timeout=timeout)
            elif action_type == "WaitFor":
                self._wait_for_visible(command, locator, timeout)
            else:
                result["text"] = (locator.inner_text(timeout=timeout) or "")[:8000]
        elif action_type == "PressKey":
            selector = getattr(action, "selector", None)
            key = str(action.key)
            if selector:
                self._locator(page, str(selector)).press(key, timeout=timeout)
            else:
                page.keyboard.press(key)
        elif action_type == "Scroll":
            direction = str(action.direction)
            if action.direction is None or action.amount is None:
                raise ValueError("Scroll requires direction and amount")
            amount = action.amount
            dx = amount if direction == "right" else -amount if direction == "left" else 0
            dy = amount if direction == "down" else -amount if direction == "up" else 0
            page.mouse.wheel(dx, dy)
        else:
            raise ValueError("unsupported closed browser action")
        page.wait_for_timeout(50)
        self._raise_if_cancelled(command)
        self._validate_pages(session)
        session.previous_action_result = result
        return BrowserActionResult(
            result=result,
            observation=self._observe(browser_session_id, session, command),
        )

    def close(self, command: BoundBrowserCommand, browser_session_id: str) -> None:
        session = self._sessions.get(browser_session_id)
        if session is None:
            return
        if session.command_identity != self._command_identity(command):
            raise PermissionError("bound browser command identity mismatch")
        session.context.close()
        if len(self._sessions) == 1:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
        self._sessions.pop(browser_session_id, None)

    def owns(self, command: BoundBrowserCommand, browser_session_id: str) -> bool:
        session = self._sessions.get(browser_session_id)
        return session is not None and session.command_identity == self._command_identity(command)

    def cancel(
        self, command: BoundBrowserCommand, browser_session_id: str | None
    ) -> None:
        identity = self._command_identity(command)
        try:
            if browser_session_id is not None:
                self.close(command, browser_session_id)
                return
            matching = [
                session_id
                for session_id, session in self._sessions.items()
                if session.command_identity == identity
            ]
            for session_id in matching:
                self.close(command, session_id)
        finally:
            with self._cancel_lock:
                self._cancelled_identities.discard(identity)

    def request_cancel(self, command: BoundBrowserCommand) -> None:
        """Signal an in-flight operation before closure runs on the Browser thread."""
        with self._cancel_lock:
            self._cancelled_identities.add(self._command_identity(command))

    def shutdown(self) -> None:
        """Close all process-owned Browser resources during graceful Agent shutdown."""
        for session in tuple(self._sessions.values()):
            session.context.close()
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._sessions.clear()
        with self._cancel_lock:
            self._cancelled_identities.clear()

    def _raise_if_cancelled(self, command: BoundBrowserCommand) -> None:
        with self._cancel_lock:
            cancelled = self._command_identity(command) in self._cancelled_identities
        if cancelled:
            raise PermissionError("bound browser command was cancelled")

    def _wait_for_visible(
        self, command: BoundBrowserCommand, locator: Locator, timeout_ms: float
    ) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            self._raise_if_cancelled(command)
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            try:
                locator.wait_for(state="visible", timeout=min(remaining_ms, 250))
                return
            except PlaywrightTimeoutError:
                if time.monotonic() >= deadline:
                    raise

    def _session(self, command: BoundBrowserCommand, browser_session_id: str) -> _Session:
        session = self._sessions.get(browser_session_id)
        if session is None or session.command_identity != self._command_identity(command):
            raise PermissionError("bound browser session identity is not current")
        return session

    def _watch_page(self, session: _Session, page: Page) -> None:
        def check(frame: Any) -> None:
            if frame != page.main_frame:
                return
            url = frame.url
            if url and url != "about:blank" and self._origin(url) not in session.allowed_origins:
                session.navigation_violation = url

        page.on("framenavigated", check)

    def _route_navigation(self, session: _Session, route: Route) -> None:
        request = route.request
        if (
            request.is_navigation_request()
            and self._origin(request.url) not in session.allowed_origins
        ):
            session.navigation_violation = request.url
            route.abort("blockedbyclient")
            return
        route.continue_()

    @staticmethod
    def _configure_captcha_capture(session: _Session, command: BoundBrowserCommand) -> None:
        material = command.login_material
        if (
            material.captcha_policy == "RESPONSE_HEADER"
            and material.captcha_request_header_name
            and material.captcha_request_header_value
        ):
            session.context.set_extra_http_headers(
                {material.captcha_request_header_name: material.captcha_request_header_value}
            )
        if (
            material.captcha_policy != "RESPONSE_HEADER"
            or not material.captcha_response_header_name
        ):
            return
        response_name = material.captcha_response_header_name.casefold()

        def capture(response: Any) -> None:
            value = {str(k).casefold(): str(v) for k, v in response.headers.items()}.get(
                response_name
            )
            if value:
                session.captcha_value = value[:4000]

        session.context.on("response", capture)

    @staticmethod
    def _apply_storage(
        session: _Session, command: BoundBrowserCommand, *, before_login: bool
    ) -> None:
        entries = [
            {"key": item.key, "value": item.value}
            for item in command.login_material.local_storage_presets
            if bool(item.set_before_login) is before_login
        ]
        if not entries:
            return
        blocked = ("password", "secret", "token", "cookie", "auth", "session")
        if any(any(marker in item["key"].casefold() for marker in blocked) for item in entries):
            raise PermissionError("secret-bearing localStorage preset denied")
        session.page.evaluate(
            "entries => { for (const item of entries) "
            "localStorage.setItem(item.key, item.value); }",
            entries,
        )
        if before_login and command.login_material.refresh_after_local_storage:
            session.page.reload(
                wait_until="domcontentloaded",
                timeout=PlaywrightBoundBrowserRuntime._timeout_ms(command),
            )

    def _perform_login(self, session: _Session, command: BoundBrowserCommand) -> None:
        page = session.page
        timeout = self._timeout_ms(command)
        password = page.locator('input[type="password"]')
        if password.count() == 0 or not password.first.is_visible():
            session.login_state_marker = {
                "status": "NOT_OBSERVED",
                "signal": "LOGIN_FORM_NOT_PRESENT",
                "login_submitted": False,
            }
            return
        login_url_before_submit = page.url
        username = page.locator(
            'input[autocomplete="username"],input[type="email"],'
            'input[name*="user" i],input[name*="account" i]'
        )
        if username.count() > 0 and username.first.is_visible():
            username.first.fill(command.login_material.account_identifier, timeout=timeout)
        password.first.fill(command.login_material.secret_value, timeout=timeout)
        captcha = page.locator('input[name*="captcha" i],input[autocomplete="one-time-code"]')
        if session.captcha_value and captcha.count() > 0 and captcha.first.is_visible():
            captcha.first.fill(session.captcha_value, timeout=timeout)
        submit = page.locator('button[type="submit"],input[type="submit"]')
        if submit.count() > 0 and submit.first.is_visible():
            submit.first.click(timeout=timeout)
        else:
            password.first.press("Enter", timeout=timeout)
        signal = self._wait_for_login_success(
            session, command, password, login_url_before_submit
        )
        session.login_state_marker = {
            "status": "SUCCEEDED",
            "signal": signal,
            "login_submitted": True,
        }

    def _wait_for_login_success(
        self,
        session: _Session,
        command: BoundBrowserCommand,
        password: Locator,
        login_url_before_submit: str,
    ) -> str:
        deadline = time.monotonic() + self._timeout_ms(command) / 1000
        while True:
            self._raise_if_cancelled(command)
            self._validate_pages(session)
            password_visible = password.count() > 0 and password.first.is_visible()
            if not password_visible:
                if session.page.url != login_url_before_submit:
                    return "AUTHENTICATED_URL"
                return "LOGIN_FORM_DISAPPEARED"
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            if remaining_ms <= 1:
                raise RuntimeError("observable login success signal was not observed")
            try:
                password.first.wait_for(state="hidden", timeout=min(remaining_ms, 250))
            except PlaywrightTimeoutError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("observable login success signal was not observed") from None

    def _validate_pages(self, session: _Session) -> None:
        if session.navigation_violation is not None:
            raise PermissionError("navigation origin denied")
        pages = list(session.context.pages)
        for candidate in pages:
            url = candidate.url
            if url and url != "about:blank" and self._origin(url) not in session.allowed_origins:
                if candidate != session.page:
                    candidate.close()
                raise PermissionError("popup, new-tab, or redirect origin denied")
        if pages:
            session.page = pages[-1]

    def _observe(
        self, browser_session_id: str, session: _Session, command: BoundBrowserCommand
    ) -> BrowserObservation:
        page = session.page
        timeout = self._timeout_ms(command)
        body_text = ""
        with suppress(Exception):
            body_text = page.locator("body").inner_text(timeout=timeout)[:12000]
        semantic: list[dict[str, object]] = []
        controls = page.locator("a,button,input,select,textarea,[role]")
        for index in range(min(controls.count(), 50)):
            item = controls.nth(index)
            try:
                if not item.is_visible():
                    continue
                semantic.append(
                    {
                        "kind": item.get_attribute("type"),
                        "role": item.get_attribute("role"),
                        "name": (
                            item.get_attribute("aria-label")
                            or item.get_attribute("name")
                            or item.inner_text(timeout=timeout)
                        )[:500],
                        "test_id": item.get_attribute("data-testid"),
                    }
                )
            except Exception:
                continue
        focused: dict[str, object] | None = None
        focus = page.locator(":focus")
        if focus.count():
            focused = {
                "role": focus.first.get_attribute("role"),
                "name": focus.first.get_attribute("aria-label")
                or focus.first.get_attribute("name"),
            }
        observation = {
            "current_url": self._sanitized_url(page.url),
            "title": page.title(),
            "visible_semantic_elements": semantic,
            "relevant_text_and_controls": body_text,
            "focused_element": focused,
            "previous_action_result": session.previous_action_result,
            "navigation_or_error": None,
            "necessary_local_accessibility_or_dom_slice": None,
            "artifact_references": [],
            "login_state_marker": session.login_state_marker,
        }
        return BrowserObservation(
            browser_session_id=browser_session_id,
            data=cast(
                dict[str, object],
                self._redact_runtime_secrets(observation, command, session.captcha_value),
            ),
        )

    @classmethod
    def _redact_runtime_secrets(
        cls,
        value: object,
        command: BoundBrowserCommand,
        captcha_value: str | None = None,
    ) -> object:
        secrets = {
            command.login_material.account_identifier,
            command.login_material.secret_value,
            command.login_material.captcha_request_header_value,
            *(item.value for item in command.login_material.local_storage_presets),
            captcha_value,
        }
        sensitive = tuple(item for item in secrets if isinstance(item, str) and item)
        if isinstance(value, str):
            redacted = value
            for secret in sensitive:
                redacted = redacted.replace(secret, "[REDACTED]")
            return redacted
        if isinstance(value, list):
            return [cls._redact_runtime_secrets(item, command, captcha_value) for item in value]
        if isinstance(value, dict):
            return {
                key: cls._redact_runtime_secrets(item, command, captcha_value)
                for key, item in value.items()
            }
        return value

    def _ensure_browser(self) -> None:
        if self._playwright is not None:
            return
        playwright = sync_playwright().start()
        try:
            browser = playwright.chromium.launch(
                headless=self._headless,
                args=["--no-proxy-server"],
            )
        except Exception:
            playwright.stop()
            raise
        self._playwright = playwright
        self._browser = browser

    def _shutdown_if_idle(self) -> None:
        if self._sessions:
            return
        if self._browser is not None:
            with suppress(Exception):
                self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with suppress(Exception):
                self._playwright.stop()
            self._playwright = None

    @staticmethod
    def _sanitized_url(value: str) -> str:
        try:
            parts = urlsplit(value)
        except ValueError:
            return value.split("?", 1)[0].split("#", 1)[0]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _locator(page: Page, selector: str) -> Locator:
        if selector.startswith("role="):
            match = re.fullmatch(r"role=([^|]+)(?:\|name=(.+))?", selector)
            if match is None:
                raise ValueError("invalid role selector")
            return page.get_by_role(cast(Any, match.group(1)), name=match.group(2))
        if selector.startswith("label="):
            return page.get_by_label(selector[6:])
        if selector.startswith("placeholder="):
            return page.get_by_placeholder(selector[12:])
        if selector.startswith("testid="):
            return page.get_by_test_id(selector[7:])
        if selector.startswith("css="):
            css = selector[4:]
            if "nth-child" in css or re.search(r"\.[A-Za-z0-9_-]{20,}", css):
                raise ValueError("unstable generated selector denied")
            return page.locator(css)
        if selector.startswith("xpath="):
            return page.locator(selector)
        raise ValueError("selector must use an approved semantic or explicit fallback form")

    @classmethod
    def _allowed_origins(cls, command: BoundBrowserCommand) -> frozenset[str]:
        values = [
            *tuple(command.allowed_origins),
            *tuple(command.authentication_redirect_origins),
        ]
        return frozenset(origin for item in values if (origin := cls._origin(str(item))))

    @classmethod
    def _require_allowed(cls, url: str, allowed: frozenset[str]) -> None:
        origin = cls._origin(url)
        if origin is None or origin not in allowed:
            raise PermissionError("navigation origin denied")

    @staticmethod
    def _origin(value: str) -> str | None:
        try:
            parts = urlsplit(value)
            if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
                return None
            port = parts.port
        except ValueError:
            return None
        default = (parts.scheme.lower() == "http" and port == 80) or (
            parts.scheme.lower() == "https" and port == 443
        )
        suffix = "" if port is None or default else f":{port}"
        return f"{parts.scheme.lower()}://{parts.hostname.lower()}{suffix}"

    @staticmethod
    def _command_identity(command: BoundBrowserCommand) -> tuple[str, str, str, int, int]:
        return (
            str(command.runner_id),
            str(command.execution_attempt_id),
            str(command.execution_binding_snapshot_id),
            int(command.identity_lease_generation),
            int(command.runner_lease_generation),
        )

    @staticmethod
    def _timeout_ms(command: BoundBrowserCommand) -> float:
        return max(1, int(command.action_timeout_seconds)) * 1000
