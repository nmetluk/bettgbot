"""Tests for security headers middleware (TASK-037)."""

from __future__ import annotations

import re
from pathlib import Path
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
        assert "https://cdn.jsdelivr.net" not in csp
        assert "style-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "form-action 'self'" in csp

    def test_csp_allows_google_fonts(self):
        """CSP allows Google Fonts for Material Symbols (TASK-057)."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")
        csp = response.headers.get("Content-Security-Policy")

        assert csp is not None
        # CSS for Material Symbols
        assert "https://fonts.googleapis.com" in csp
        # Font files from gstatic
        assert "font-src 'self' https://fonts.gstatic.com" in csp

    def test_csp_no_external_cdn_after_selfhost(self):
        """CSP has no jsdelivr.net after TASK-079 self-host vendoring (supply-chain hardening)."""
        app = FastAPI()

        @app.get("/")
        def read_root():
            return {"status": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/")
        csp = response.headers.get("Content-Security-Policy")

        assert csp is not None
        assert "https://cdn.jsdelivr.net" not in csp
        # script-src is now strictly 'self' (no external CDNs)
        assert "script-src 'self'" in csp
        # Alpine CSP build (vendored) doesn't require unsafe-eval
        assert "unsafe-eval" not in csp

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
            "Content-Security-Policy": lambda v: (
                all(
                    x in v
                    for x in [
                        "default-src 'self'",
                        "script-src 'self'",
                        "frame-ancestors 'none'",
                        "https://fonts.googleapis.com",
                        "https://fonts.gstatic.com",
                    ]
                )
                and "https://cdn.jsdelivr.net" not in v
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

    def test_no_inline_event_handlers_in_templates(self):
        """CSP guard: no inline on*= handlers allowed in admin templates (TASK-084).

        Prevents regression of script-src 'self' violations (blocks navigation, confirms etc).
        Uses static scan so it catches even unrendered templates.
        """
        templates_dir = Path(__file__).resolve().parents[3] / "src" / "admin" / "templates"
        assert templates_dir.exists(), f"Templates dir not found at {templates_dir}"

        pattern = re.compile(r"on(?:click|change|submit|input|load)\s*=", re.IGNORECASE)
        offenders: list[str] = []

        for html_file in sorted(templates_dir.rglob("*.html")):
            try:
                content = html_file.read_text(encoding="utf-8")
            except Exception as exc:
                offenders.append(f"{html_file.name}: read error: {exc}")
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    offenders.append(
                        f"{html_file.relative_to(templates_dir)}:{lineno}: {line.strip()[:100]}"
                    )

        assert not offenders, (
            "Inline event handlers (onclick= etc) found in admin templates — this violates strict CSP "
            "`script-src 'self'` (no 'unsafe-inline'). Use data-href / data-confirm + delegation in "
            "ui.js (or plain <a href> for tabs). Offenders:\n" + "\n".join(offenders)
        )
