"""Тесты для `src.shared.logging`."""

from __future__ import annotations

import json
import logging
import re

import pytest
from src.shared.logging import configure_logging, get_logger

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Сбрасывает handlers root-logger'а после каждого теста."""
    yield
    logging.getLogger().handlers.clear()


def _captured(capsys: pytest.CaptureFixture[str]) -> str:
    out = capsys.readouterr()
    return _ANSI_RE.sub("", out.err + out.out)


def test_logging_json_format(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "json")
    get_logger("test").info("login_attempt", user_id=42, source="bot")

    output = _captured(capsys)
    line = next((s for s in output.splitlines() if "login_attempt" in s), None)
    assert line is not None, f"event not found: {output!r}"

    payload = json.loads(line)
    assert payload["event"] == "login_attempt"
    assert payload["user_id"] == 42
    assert payload["source"] == "bot"
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_logging_console_format(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "console")
    get_logger("test").info("some_event", x=1)

    output = _captured(capsys)
    assert "some_event" in output
    assert "x=1" in output


def test_logging_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "json")
    configure_logging("INFO", "json")
    configure_logging("INFO", "json")
    get_logger("test").info("once_only")

    output = _captured(capsys)
    event_lines = [s for s in output.splitlines() if "once_only" in s]
    assert len(event_lines) == 1, f"expected one line, got: {event_lines}"


def test_logging_json_processor_chain() -> None:
    """При json-формате в chain должен быть JSONRenderer."""
    import structlog

    configure_logging("INFO", "json")
    config = structlog.get_config()
    # ProcessorFormatter с JSONRenderer внутри
    assert any("ProcessorFormatter" in str(p) for p in config["processors"])


def test_logging_console_processor_chain() -> None:
    """При console-формате должен быть ConsoleRenderer."""
    import structlog

    configure_logging("INFO", "console")
    config = structlog.get_config()
    # ProcessorFormatter с ConsoleRenderer внутри
    assert any("ProcessorFormatter" in str(p) for p in config["processors"])
