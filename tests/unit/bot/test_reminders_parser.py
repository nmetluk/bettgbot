"""Тесты `parse_offset` — парсера свободного ввода интервала напоминаний."""

from __future__ import annotations

import pytest
from src.bot._reminders_parser import parse_offset


@pytest.mark.parametrize("raw,expected", [("15", 15), ("60", 60), ("10080", 10080)])
def test_parse_offset_minutes_no_suffix(raw: str, expected: int) -> None:
    assert parse_offset(raw) == expected


@pytest.mark.parametrize("raw,expected", [("15m", 15), ("15M", 15), ("60m", 60)])
def test_parse_offset_minutes_m_suffix(raw: str, expected: int) -> None:
    assert parse_offset(raw) == expected


@pytest.mark.parametrize("raw,expected", [("1h", 60), ("3H", 180), ("12h", 720)])
def test_parse_offset_hours(raw: str, expected: int) -> None:
    assert parse_offset(raw) == expected


@pytest.mark.parametrize("raw,expected", [("1d", 1440), ("2d", 2880), ("7d", 10080)])
def test_parse_offset_days(raw: str, expected: int) -> None:
    assert parse_offset(raw) == expected


@pytest.mark.parametrize("raw", ["3", "4", "0", "4m"])
def test_parse_offset_below_minimum_returns_none(raw: str) -> None:
    assert parse_offset(raw) is None


@pytest.mark.parametrize("raw", ["10081", "20000", "8d", "169h"])
def test_parse_offset_above_maximum_returns_none(raw: str) -> None:
    assert parse_offset(raw) is None


@pytest.mark.parametrize("raw", ["abc", "1.5h", "", "15z", "h15", "1 5"])
def test_parse_offset_invalid_format_returns_none(raw: str) -> None:
    assert parse_offset(raw) is None


@pytest.mark.parametrize("raw,expected", [("  15  ", 15), (" 15m ", 15), ("\t60\n", 60)])
def test_parse_offset_whitespace_tolerated(raw: str, expected: int) -> None:
    assert parse_offset(raw) == expected
