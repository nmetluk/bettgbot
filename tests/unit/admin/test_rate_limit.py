"""Tests for rate limiting (TASK-038)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app


@pytest.fixture
def client():
    """Test client with mocked rate limiter."""
    from fastapi_csrf_protect import CsrfProtect

    # Mock CSRF to bypass validation
    mock_csrf = MagicMock(spec=CsrfProtect)
    mock_csrf.validate_csrf = AsyncMock(return_value=None)

    # Mock FastAPILimiter
    with patch("src.admin.routes.login.fastapi_limiter") as mock_limiter:
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.__call__ = AsyncMock(return_value=None)
        mock_limiter.RateLimiter = MagicMock(return_value=mock_rate_limiter)

        app.dependency_overrides.clear()
        client = TestClient(app, follow_redirects=False)
        yield client


class TestLoginRateLimitIdentifier:
    """Rate limit identifier uses IP + login combination."""

    def test_identifier_uses_client_host_and_login(self):
        """The identifier function extracts login from form data."""
        from src.admin.routes.login import _login_rate_limit_identifier

        async def test_identifier():
            # Create a mock request
            mock_request = MagicMock()
            mock_request.client = MagicMock()
            mock_request.client.host = "192.168.1.100"

            # Mock form data
            mock_form = MagicMock()
            mock_form.get = MagicMock(return_value="testuser")
            mock_request.form = AsyncMock(return_value=mock_form)

            # Call identifier
            result = await _login_rate_limit_identifier(mock_request)

            # Should be "IP:login" format
            assert result == "192.168.1.100:testuser"

        import asyncio

        asyncio.run(test_identifier())

    def test_identifier_handles_missing_client(self):
        """Identifier handles case where request.client is None."""
        from src.admin.routes.login import _login_rate_limit_identifier

        async def test_identifier():
            mock_request = MagicMock()
            mock_request.client = None

            mock_form = MagicMock()
            mock_form.get = MagicMock(return_value="testuser")
            mock_request.form = AsyncMock(return_value=mock_form)

            result = await _login_rate_limit_identifier(mock_request)

            assert result == ":testuser"

        import asyncio

        asyncio.run(test_identifier())

    def test_identifier_handles_form_parse_error(self):
        """Identifier handles form parsing errors gracefully."""
        from src.admin.routes.login import _login_rate_limit_identifier

        async def test_identifier():
            mock_request = MagicMock()
            mock_request.client = MagicMock()
            mock_request.client.host = "10.0.0.1"

            # Form parsing raises exception
            mock_request.form = AsyncMock(side_effect=Exception("Parse error"))

            result = await _login_rate_limit_identifier(mock_request)

            # Should fall back to empty login
            assert result == "10.0.0.1:"

        import asyncio

        asyncio.run(test_identifier())

    def test_login_route_exists(self):
        """The /login route exists (rate limit configured via dependency)."""
        # Find the login_submit route
        for route in app.routes:
            if (
                hasattr(route, "path")
                and route.path == "/login"
                and hasattr(route, "methods")
                and "POST" in route.methods
            ):
                # Route exists - rate limit is configured via dependency in login.py
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
