"""Tests for rate limiting (TASK-038)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app


class TestLoginRateLimit:
    """Rate limiting on /login endpoint."""

    def test_rate_limit_function_exists(self):
        """The rate limit function exists and is importable."""
        from src.admin.routes.login import _login_rate_limit

        assert callable(_login_rate_limit)

    def test_rate_limit_function_skips_when_redis_not_set(self):
        """Rate limit returns early when FastAPILimiter.redis is None (tests)."""
        from src.admin.routes.login import _login_rate_limit

        async def test_func():
            mock_request = MagicMock()
            mock_request.client = MagicMock()
            mock_request.client.host = "192.168.1.100"

            mock_form = MagicMock()
            mock_form.get = MagicMock(return_value="testuser")
            mock_request.form = AsyncMock(return_value=mock_form)

            # Mock FastAPILimiter.redis as None
            with patch("fastapi_limiter.FastAPILimiter") as mock_limiter:
                mock_limiter.redis = None

                # Should return early without error
                await _login_rate_limit(mock_request)

        import asyncio

        asyncio.run(test_func())

    def test_login_route_exists(self):
        """The /login route exists (rate limit configured via dependency)."""
        for route in app.routes:
            if (
                hasattr(route, "path")
                and route.path == "/login"
                and hasattr(route, "methods")
                and "POST" in route.methods
            ):
                return

        pytest.fail("POST /login route not found")


class TestProxyHeadersConfig:
    """Uvicorn configured for proxy headers."""

    def test_dockerfile_has_proxy_headers(self):
        """Dockerfile.web includes --proxy-headers flag."""
        from pathlib import Path

        dockerfile_path = Path(__file__).parent.parent.parent.parent / "infra" / "Dockerfile.web"
        content = dockerfile_path.read_text()

        assert "--proxy-headers" in content
        assert "--forwarded-allow-ips=*" in content
        assert "--workers" in content
        assert "--limit-concurrency" in content
        assert "--limit-max-requests" in content
        assert "--timeout-keep-alive" in content


class TestNginxRateLimit:
    """Nginx configuration includes rate limiting."""

    def test_nginx_has_rate_limit_zones(self):
        """Nginx config has limit_req_zone directives."""
        from pathlib import Path

        nginx_conf = (
            Path(__file__).parent.parent.parent.parent / "infra" / "nginx" / "admin.conf.template"
        )
        content = nginx_conf.read_text()

        assert "limit_req_zone" in content
        assert "zone=login" in content
        assert "zone=app" in content
        assert "rate=10r/m" in content  # login zone
        assert "rate=60r/m" in content  # app zone

    def test_nginx_has_slowloris_protection(self):
        """Nginx config has timeout directives for slowloris protection."""
        from pathlib import Path

        nginx_conf = (
            Path(__file__).parent.parent.parent.parent / "infra" / "nginx" / "admin.conf.template"
        )
        content = nginx_conf.read_text()

        assert "client_body_timeout" in content
        assert "client_header_timeout" in content
        assert "send_timeout" in content
        assert "keepalive_timeout" in content

    def test_nginx_has_keepalive_to_backend(self):
        """Nginx config uses keepalive to backend."""
        from pathlib import Path

        nginx_conf = (
            Path(__file__).parent.parent.parent.parent / "infra" / "nginx" / "admin.conf.template"
        )
        content = nginx_conf.read_text()

        assert "upstream web_backend" in content
        assert "keepalive 32" in content
        assert "proxy_http_version 1.1" in content
        assert 'proxy_set_header Connection ""' in content

    def test_nginx_has_reduced_max_body_size(self):
        """Nginx client_max_body_size is reduced to 256k."""
        from pathlib import Path

        nginx_conf = (
            Path(__file__).parent.parent.parent.parent / "infra" / "nginx" / "admin.conf.template"
        )
        content = nginx_conf.read_text()

        assert "client_max_body_size 256k" in content
