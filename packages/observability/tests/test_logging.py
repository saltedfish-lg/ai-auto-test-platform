import io
import json
import logging

from platform_observability import JsonFormatter, correlation_context


def _logger(stream: io.StringIO) -> logging.Logger:
    logger = logging.getLogger("test.secure-logging")
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def test_sensitive_values_are_not_written_to_logs() -> None:
    stream = io.StringIO()
    logger = _logger(stream)

    logger.info(
        "authorization=Bearer raw-token password=hunter2",
        extra={"api_key": "sk-real-looking", "nested": {"refresh_token": "token-value"}},
    )

    rendered = stream.getvalue()
    assert "raw-token" not in rendered
    assert "hunter2" not in rendered
    assert "sk-real-looking" not in rendered
    assert "token-value" not in rendered
    assert "***REDACTED***" in rendered


def test_correlation_id_is_structured_and_context_is_reset() -> None:
    stream = io.StringIO()
    logger = _logger(stream)

    with correlation_context("correlation-123"):
        logger.info("ready")
    logger.info("outside")

    first, second = (json.loads(line) for line in stream.getvalue().splitlines())
    assert first["correlation_id"] == "correlation-123"
    assert "correlation_id" not in second
