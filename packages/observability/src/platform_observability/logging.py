"""JSON logging that removes secret-bearing keys and common inline credentials."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from platform_observability.context import get_correlation_id

REDACTED = "***REDACTED***"
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "cookie",
    "credential",
    "api_key",
    "apikey",
    "database_url",
)
INLINE_SECRET = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)\s*[:=]\s*([^\s,;]+)"
)
BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/]+=*")
STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _sanitize_text(value: str) -> str:
    value = BEARER_TOKEN.sub(f"Bearer {REDACTED}", value)
    value = INLINE_SECRET.sub(lambda match: f"{match.group(1)}={REDACTED}", value)
    return value


def sanitize(value: object, *, key: str = "") -> object:
    if key and _is_sensitive(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): sanitize(child, key=str(child_key))
            for child_key, child in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [sanitize(child) for child in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return _sanitize_text(str(value))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize(record.getMessage()),
        }
        if correlation_id := get_correlation_id():
            document["correlation_id"] = correlation_id
        for key, value in record.__dict__.items():
            if key not in STANDARD_RECORD_FIELDS and not key.startswith("_"):
                document[key] = sanitize(value, key=key)
        if record.exc_info:
            document["exception"] = sanitize(self.formatException(record.exc_info))
        return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"unsupported log level: {level}")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)
