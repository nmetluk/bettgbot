"""Тесты `MockExternalUserRegistryClient` и `load_mock_config`."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from src.shared.external import (
    AllowedEntry,
    ExternalApiError,
    MockExternalUserRegistryClient,
    load_mock_config,
)


async def test_allowed_returns_is_allowed_true() -> None:
    client = MockExternalUserRegistryClient(
        allowed={"+71": AllowedEntry(external_user_id="u-1", display_name="Alice")},
        blocked={},
    )
    result = await client.verify("+71")
    assert result.is_allowed is True
    assert result.external_user_id == "u-1"
    assert result.display_name == "Alice"
    assert result.reason is None


async def test_not_found_returns_is_allowed_false() -> None:
    client = MockExternalUserRegistryClient(allowed={}, blocked={})
    result = await client.verify("+700")
    assert result.is_allowed is False
    assert result.reason == "not_found"


async def test_blocked_returns_is_allowed_false_with_reason() -> None:
    client = MockExternalUserRegistryClient(allowed={}, blocked={"+79": "manual-block"})
    result = await client.verify("+79")
    assert result.is_allowed is False
    assert result.reason == "manual-block"


def test_csv_allowed_overrides_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "mock.yml"
    yaml_file.write_text(
        "allowed:\n"
        "  - phone: '+71'\n"
        "    external_user_id: 'u-1'\n"
        "blocked:\n"
        "  - phone: '+79'\n"
        "    reason: 'b'\n",
        encoding="utf-8",
    )
    cfg = load_mock_config(file=yaml_file, allowed_csv=["+72", "+73"])
    # CSV перекрывает allowed из файла; blocked при этом сохраняется.
    assert set(cfg.allowed.keys()) == {"+72", "+73"}
    assert all(entry.external_user_id is None for entry in cfg.allowed.values())
    assert cfg.blocked == {"+79": "b"}


def test_yaml_loaded_from_file(tmp_path: Path) -> None:
    yaml_file = tmp_path / "mock.yml"
    yaml_file.write_text(
        "allowed:\n"
        "  - phone: '+71'\n"
        "    external_user_id: 'u-1'\n"
        "    display_name: 'Alice'\n"
        "simulate:\n"
        "  latency_ms: 25\n"
        "  fail_rate: 0.5\n",
        encoding="utf-8",
    )
    cfg = load_mock_config(file=yaml_file, allowed_csv=[])
    assert cfg.allowed["+71"].external_user_id == "u-1"
    assert cfg.allowed["+71"].display_name == "Alice"
    assert cfg.latency_ms == 25
    assert cfg.fail_rate == 0.5


async def test_simulate_fail_rate_1_always_raises_external_api_error() -> None:
    client = MockExternalUserRegistryClient(
        allowed={"+71": AllowedEntry()}, blocked={}, fail_rate=1.0
    )
    with pytest.raises(ExternalApiError):
        await client.verify("+71")


async def test_simulate_latency_ms_awaits() -> None:
    client = MockExternalUserRegistryClient(
        allowed={"+71": AllowedEntry()}, blocked={}, latency_ms=50
    )
    start = time.monotonic()
    await client.verify("+71")
    elapsed_ms = (time.monotonic() - start) * 1000
    # asyncio.sleep даёт минимум указанное время, но может быть чуть больше.
    assert elapsed_ms >= 45
