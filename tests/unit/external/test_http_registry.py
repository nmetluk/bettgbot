"""Тесты `HttpExternalUserRegistryClient` на `httpx.MockTransport`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from src.shared.external import ExternalApiError, HttpExternalUserRegistryClient


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[
    HttpExternalUserRegistryClient,
    list[float],
    httpx.AsyncClient,
]:
    """Собирает клиент с MockTransport и записанной sleep-функцией."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    client = HttpExternalUserRegistryClient(
        base_url="http://test",
        token="tok",
        client=httpx_client,
        sleep=fake_sleep,
    )
    return client, sleeps, httpx_client


def _responses(responses: list[httpx.Response]) -> Callable[[httpx.Request], httpx.Response]:
    iter_resp: Iterator[httpx.Response] = iter(responses)

    def handler(_: httpx.Request) -> httpx.Response:
        return next(iter_resp)

    return handler


async def test_200_ok_returns_allowed() -> None:
    handler = _responses(
        [
            httpx.Response(
                200,
                json={
                    "status": "ok",
                    "external_user_id": "u-1",
                    "display_name": "Alice",
                },
            )
        ]
    )
    client, _, ac = _client(handler)
    try:
        result = await client.verify("+71")
        assert result.is_allowed is True
        assert result.external_user_id == "u-1"
        assert result.display_name == "Alice"
    finally:
        await ac.aclose()


async def test_200_not_found() -> None:
    handler = _responses([httpx.Response(200, json={"status": "not_found"})])
    client, _, ac = _client(handler)
    try:
        result = await client.verify("+72")
        assert result.is_allowed is False
        assert result.reason == "not_found"
    finally:
        await ac.aclose()


async def test_200_blocked_with_reason() -> None:
    handler = _responses([httpx.Response(200, json={"status": "blocked", "reason": "denied"})])
    client, _, ac = _client(handler)
    try:
        result = await client.verify("+73")
        assert result.is_allowed is False
        assert result.reason == "denied"
    finally:
        await ac.aclose()


async def test_401_unauthorized_raises_no_retry() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    client, sleeps, ac = _client(handler)
    try:
        with pytest.raises(ExternalApiError, match="unauthorized"):
            await client.verify("+74")
        assert calls["n"] == 1
        assert sleeps == []
    finally:
        await ac.aclose()


async def test_5xx_then_200_succeeds_after_retry() -> None:
    handler = _responses(
        [
            httpx.Response(500),
            httpx.Response(200, json={"status": "ok", "external_user_id": "u-1"}),
        ]
    )
    client, sleeps, ac = _client(handler)
    try:
        result = await client.verify("+71")
        assert result.is_allowed is True
        assert sleeps == [0.5]
    finally:
        await ac.aclose()


async def test_5xx_three_times_raises_external_api_error() -> None:
    handler = _responses([httpx.Response(500), httpx.Response(502), httpx.Response(503)])
    client, sleeps, ac = _client(handler)
    try:
        with pytest.raises(ExternalApiError):
            await client.verify("+71")
        assert sleeps == [0.5, 1.0]
    finally:
        await ac.aclose()


async def test_429_with_retry_after_respected() -> None:
    handler = _responses(
        [
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json={"status": "ok", "external_user_id": "u-1"}),
        ]
    )
    client, sleeps, ac = _client(handler)
    try:
        result = await client.verify("+71")
        assert result.is_allowed is True
        assert sleeps == [3.0]
    finally:
        await ac.aclose()


async def test_request_includes_phone_in_body_and_auth_header() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["auth"] = request.headers.get("Authorization")
        captured["xid"] = request.headers.get("X-Request-Id")
        return httpx.Response(200, json={"status": "not_found"})

    client, _, ac = _client(handler)
    try:
        await client.verify("+71234567890")
        assert b'"phone":"+71234567890"' in captured["body"]
        assert captured["auth"] == "Bearer tok"
        assert captured["xid"] and len(captured["xid"]) >= 16
    finally:
        await ac.aclose()


async def test_request_generates_x_request_id_per_call() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-Request-Id"))
        return httpx.Response(200, json={"status": "not_found"})

    client, _, ac = _client(handler)
    try:
        await client.verify("+71")
        await client.verify("+72")
        assert seen[0] != seen[1]
    finally:
        await ac.aclose()


async def test_timeout_raises_external_api_error_after_retries() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timeout", request=None)

    client, sleeps, ac = _client(handler)
    try:
        with pytest.raises(ExternalApiError):
            await client.verify("+71")
        # Изначальная попытка + 2 ретрая = 3 вызова.
        assert calls["n"] == 3
        assert sleeps == [0.5, 1.0]
    finally:
        await ac.aclose()
