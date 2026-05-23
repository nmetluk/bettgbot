"""`HttpExternalUserRegistryClient` — реализация на `httpx.AsyncClient`.

Контракт API и retry-политика — `docs/06-external-api.md`. Логи структурные:
`external_api.endpoint/phone_hash/status_code/latency_ms/retry_count/outcome`.
PII (телефон) не светим — только sha256[:8].
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from typing import Any

import httpx

from ..logging import get_logger
from .registry import ExternalApiError, VerificationResult

__all__ = ["HttpExternalUserRegistryClient"]


_logger = get_logger(__name__)

# Retry-политика: 2 ретрая для 5xx/сети с экспоненциальным бэкоффом + 1 для 429.
_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0)
_MAX_RETRIES_5XX = len(_BACKOFF_SECONDS)


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()[:8]


def _parse_retry_after(value: str | None) -> float:
    """Парсит заголовок `Retry-After` (только секунды). Невалидное → 0."""
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0


class HttpExternalUserRegistryClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_connect: float = 2.0,
        timeout_read: float = 5.0,
        client: httpx.AsyncClient | None = None,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._owns_client = client is None
        if client is None:
            timeout = httpx.Timeout(
                connect=timeout_connect,
                read=timeout_read,
                write=timeout_read,
                pool=timeout_read,
            )
            client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)
        self._client = client
        # Подменяемая sleep-функция для тестов retry-логики.
        self._sleep = sleep

    async def __aenter__(self) -> HttpExternalUserRegistryClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def verify(self, phone: str) -> VerificationResult:
        request_id = uuid.uuid4().hex
        headers = {
            "Authorization": f"Bearer {self._token}",
            "X-Request-Id": request_id,
        }
        body = {"phone": phone}
        url = f"{self._base_url}/users/verify"

        start = time.monotonic()
        retry_count = 0
        last_exception: Exception | None = None

        while True:
            try:
                response = await self._client.post(url, json=body, headers=headers)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exception = exc
                if retry_count < _MAX_RETRIES_5XX:
                    await self._sleep(_BACKOFF_SECONDS[retry_count])
                    retry_count += 1
                    continue
                self._log_outcome(
                    phone=phone,
                    status_code=None,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    retry_count=retry_count,
                    outcome="error",
                )
                raise ExternalApiError("network error", cause=exc) from exc

            status = response.status_code

            if status == 200:
                result = self._parse_ok(response)
                self._log_outcome(
                    phone=phone,
                    status_code=status,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    retry_count=retry_count,
                    outcome=result.reason if result.reason in ("not_found", "blocked") else "ok",
                )
                return result

            if status == 401:
                self._log_outcome(
                    phone=phone,
                    status_code=status,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    retry_count=retry_count,
                    outcome="error",
                )
                raise ExternalApiError("unauthorized")

            if status == 429:
                # Один ретрай с уважением Retry-After (после первого 429 — больше не ретраим).
                if retry_count == 0:
                    delay = _parse_retry_after(response.headers.get("Retry-After"))
                    await self._sleep(delay)
                    retry_count += 1
                    continue
                self._log_outcome(
                    phone=phone,
                    status_code=status,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    retry_count=retry_count,
                    outcome="error",
                )
                raise ExternalApiError("rate limited")

            if 500 <= status < 600:
                if retry_count < _MAX_RETRIES_5XX:
                    await self._sleep(_BACKOFF_SECONDS[retry_count])
                    retry_count += 1
                    continue
                self._log_outcome(
                    phone=phone,
                    status_code=status,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    retry_count=retry_count,
                    outcome="error",
                )
                raise ExternalApiError(f"server error {status}")

            # 4xx кроме 401/429 — не ретраим.
            self._log_outcome(
                phone=phone,
                status_code=status,
                latency_ms=int((time.monotonic() - start) * 1000),
                retry_count=retry_count,
                outcome="error",
            )
            raise ExternalApiError(f"unexpected status {status}")

        # Линтеры не доходят сюда — все ветки выше выходят.
        raise ExternalApiError("unreachable", cause=last_exception)

    def _parse_ok(self, response: httpx.Response) -> VerificationResult:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalApiError("invalid JSON in 200 response", cause=exc) from exc
        status = payload.get("status")
        if status == "ok":
            return VerificationResult(
                is_allowed=True,
                external_user_id=payload.get("external_user_id"),
                display_name=payload.get("display_name"),
            )
        if status == "not_found":
            return VerificationResult(is_allowed=False, reason="not_found")
        if status == "blocked":
            return VerificationResult(is_allowed=False, reason=payload.get("reason") or "blocked")
        raise ExternalApiError(f"unknown status in 200 response: {status!r}")

    def _log_outcome(
        self,
        *,
        phone: str,
        status_code: int | None,
        latency_ms: int,
        retry_count: int,
        outcome: str,
    ) -> None:
        _logger.info(
            "external_api.verify",
            **{
                "external_api.endpoint": "users.verify",
                "external_api.phone_hash": _phone_hash(phone),
                "external_api.status_code": status_code,
                "external_api.latency_ms": latency_ms,
                "external_api.retry_count": retry_count,
                "external_api.outcome": outcome,
            },
        )
