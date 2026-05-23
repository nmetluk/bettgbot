"""Тесты фабрики `get_registry_client`."""

from __future__ import annotations

import pytest
from src.shared.config import get_settings
from src.shared.external import (
    HttpExternalUserRegistryClient,
    MockExternalUserRegistryClient,
    get_registry_client,
)


def test_get_registry_client_mock_backend_returns_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_REGISTRY_BACKEND", "mock")
    monkeypatch.setenv("MOCK_REGISTRY_ALLOWED", "+71,+72")
    monkeypatch.delenv("MOCK_REGISTRY_FILE", raising=False)
    get_settings.cache_clear()

    client = get_registry_client()
    assert isinstance(client, MockExternalUserRegistryClient)


def test_get_registry_client_http_backend_returns_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_REGISTRY_BACKEND", "http")
    monkeypatch.setenv("EXTERNAL_API_BASE_URL", "https://registry.example.com")
    monkeypatch.setenv("EXTERNAL_API_TOKEN", "secret-token")
    get_settings.cache_clear()

    client = get_registry_client()
    assert isinstance(client, HttpExternalUserRegistryClient)
