"""Tests for security headers middleware (TASK-037)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.admin._security_headers import SecurityHeadersMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


class TestSecurityHeaders:
    """Security headers middleware tests."""

    def test_csp_header_added(self):
        """CSP header is set on responses."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "https://cdn.jsdelivr.net" in csp
        assert "style-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "form-action 'self'" in csp

    def test_x_frame_options(self):
        """X-Frame-Options is DENY."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")

        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_content_type_options(self):
        """X-Content-Type-Options is nosniff."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self):
        """Referrer-Policy is strict-origin-when-cross-origin."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")

        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        """Permissions-Policy disables geolocation, camera, microphone."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")

        pp = response.headers.get("Permissions-Policy")
        assert pp is not None
        assert "geolocation=()" in pp
        assert "camera=()" in pp
        assert "microphone=()" in pp

    def test_all_headers_present_together(self):
        """All security headers are present on a single response."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")

        # Verify all headers at once
        expected_headers = {
            "Content-Security-Policy": lambda v: all(
                x in v
                for x in [
                    "default-src 'self'",
                    "script-src 'self'",
                    "https://cdn.jsdelivr.net",
                    "frame-ancestors 'none'",
                ]
            ),
            "X-Frame-Options": lambda v: v == "DENY",
            "X-Content-Type-Options": lambda v: v == "nosniff",
            "Referrer-Policy": lambda v: v == "strict-origin-when-cross-origin",
            "Permissions-Policy": lambda v: all(
                x in v for x in ["geolocation=()", "camera=()", "microphone=()"]
            ),
        }

        for header, validator in expected_headers.items():
            value = response.headers.get(header)
            assert value is not None, f"Header {header} is missing"
            assert validator(value), f"Header {header} has unexpected value: {value}"
