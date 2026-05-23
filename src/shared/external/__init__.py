"""Внешний реестр пользователей: интерфейс + фабрика + две реализации.

Фабрика `get_registry_client()` выбирает реализацию по `settings.external_registry`.
В DEV/CI — `MockExternalUserRegistryClient`; в проде (после согласования контракта) —
`HttpExternalUserRegistryClient`.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .http_registry import HttpExternalUserRegistryClient
from .mock_registry import (
    AllowedEntry,
    MockConfig,
    MockExternalUserRegistryClient,
    load_mock_config,
)
from .registry import ExternalApiError, ExternalUserRegistryClient, VerificationResult

__all__ = [
    "AllowedEntry",
    "ExternalApiError",
    "ExternalUserRegistryClient",
    "HttpExternalUserRegistryClient",
    "MockConfig",
    "MockExternalUserRegistryClient",
    "VerificationResult",
    "get_registry_client",
    "load_mock_config",
]


@lru_cache(maxsize=1)
def get_registry_client() -> ExternalUserRegistryClient:
    """Возвращает singleton-клиент реестра по конфигу.

    Кэшируется через `lru_cache`. Тесты, меняющие env, должны звать
    `get_registry_client.cache_clear()` перед повторной фабрикацией.
    """
    ext = get_settings().external_registry
    if ext.backend == "http":
        # Settings._check_http_backend_has_credentials гарантирует, что url+token заданы.
        assert ext.api_base_url is not None
        assert ext.api_token is not None
        return HttpExternalUserRegistryClient(
            base_url=str(ext.api_base_url),
            token=ext.api_token.get_secret_value(),
            timeout_connect=ext.timeout_connect,
            timeout_read=ext.timeout_read,
        )

    config = load_mock_config(
        file=ext.mock_registry_file,
        allowed_csv=ext.mock_registry_allowed,
    )
    return MockExternalUserRegistryClient(
        allowed=config.allowed,
        blocked=config.blocked,
        latency_ms=config.latency_ms,
        fail_rate=config.fail_rate,
    )
