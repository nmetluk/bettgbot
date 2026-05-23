"""`MockExternalUserRegistryClient` — реализация на основе YAML/env для разработки и тестов.

Загрузку конфига выполняет фабрика; этот модуль занят только самим клиентом и
парсингом YAML по эталону `infra/mock-registry.yml`.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .registry import ExternalApiError, VerificationResult

__all__ = ["AllowedEntry", "MockConfig", "MockExternalUserRegistryClient", "load_mock_config"]


@dataclass(frozen=True)
class AllowedEntry:
    """Запись о разрешённом телефоне: id во внешней системе + опциональное имя."""

    external_user_id: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class MockConfig:
    """Параметры mock-клиента: маппинги телефонов и симуляция сети."""

    allowed: dict[str, AllowedEntry] = field(default_factory=dict)
    blocked: dict[str, str] = field(default_factory=dict)
    latency_ms: int = 0
    fail_rate: float = 0.0


def load_mock_config(file: Path | None, allowed_csv: list[str]) -> MockConfig:
    """Загружает конфиг из YAML-файла; `allowed_csv` (env) перекрывает `allowed` файла.

    Если CSV непустой — итоговый `allowed` строится из него (с None-значениями),
    а YAML-allowed игнорируется. `blocked` и `simulate` из YAML сохраняются.
    """
    raw: dict[str, Any] = {}
    if file is not None and file.exists():
        with open(file, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                raw = loaded

    blocked: dict[str, str] = {}
    for item in raw.get("blocked", []) or []:
        phone = item.get("phone")
        if phone:
            blocked[phone] = item.get("reason") or "blocked"

    if allowed_csv:
        allowed: dict[str, AllowedEntry] = {p: AllowedEntry() for p in allowed_csv}
    else:
        allowed = {}
        for item in raw.get("allowed", []) or []:
            phone = item.get("phone")
            if phone:
                allowed[phone] = AllowedEntry(
                    external_user_id=item.get("external_user_id"),
                    display_name=item.get("display_name"),
                )

    simulate = raw.get("simulate") or {}
    latency_ms = int(simulate.get("latency_ms", 0) or 0)
    fail_rate = float(simulate.get("fail_rate", 0.0) or 0.0)

    return MockConfig(
        allowed=allowed,
        blocked=blocked,
        latency_ms=latency_ms,
        fail_rate=fail_rate,
    )


class MockExternalUserRegistryClient:
    """In-process реализация реестра по словарям разрешённых/заблокированных."""

    def __init__(
        self,
        *,
        allowed: dict[str, AllowedEntry],
        blocked: dict[str, str],
        latency_ms: int = 0,
        fail_rate: float = 0.0,
    ) -> None:
        self._allowed = allowed
        self._blocked = blocked
        self._latency_ms = latency_ms
        self._fail_rate = fail_rate

    async def verify(self, phone: str) -> VerificationResult:
        if self._fail_rate > 0 and random.random() < self._fail_rate:
            raise ExternalApiError("simulated failure (mock)")

        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)

        if phone in self._blocked:
            return VerificationResult(is_allowed=False, reason=self._blocked[phone])

        if phone in self._allowed:
            entry = self._allowed[phone]
            return VerificationResult(
                is_allowed=True,
                external_user_id=entry.external_user_id,
                display_name=entry.display_name,
            )

        return VerificationResult(is_allowed=False, reason="not_found")
