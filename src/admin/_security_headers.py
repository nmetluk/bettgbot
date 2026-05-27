"""ASGI middleware for security headers.

CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
Part of TASK-037 security hardening.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Headers added:
    - Content-Security-Policy: restricts resource sources
    - X-Frame-Options: DENY prevents clickjacking
    - X-Content-Type-Options: nosniff prevents MIME-sniffing
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: disables geolocation, camera, microphone
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)

        # CSP: allow self, cdn.jsdelivr.net for Bootstrap/HTMX, unsafe-inline for styles
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), interest-cohort=()"
        )

        return response
