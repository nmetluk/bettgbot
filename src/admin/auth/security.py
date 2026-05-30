"""Signed cookie через itsdangerous (TASK-020).

Token внутри — `{"admin_id": int}` + timestamp (внутри itsdangerous).
TTL — `Settings.admin.session_hours` часов. Sliding-TTL обеспечивает
middleware, переоформляя cookie на каждом успешном запросе.
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.shared.config import get_settings

__all__ = [
    "CSRF_COOKIE_NAME",
    "CSRF_COOKIE_NAME_PROD",
    "CSRF_TTL_SECONDS",
    "SESSION_COOKIE_NAME",
    "SESSION_COOKIE_NAME_PROD",
    "create_session_token",
    "verify_session_token",
]


# CSRF-токен живёт 15 минут (TASK-068, TASK-069)
# Значение должно совпадать с max_age в _csrf_config (app.py)
CSRF_TTL_SECONDS = 900


# Dev-имена (без __Host- префикса, с Domain possibile)
SESSION_COOKIE_NAME = "bb_admin_session"
CSRF_COOKIE_NAME = "fastapi-csrf-token"
# Prod-имена с __Host- префиксом (browser enforce'ит Path=/, Secure, без Domain)
SESSION_COOKIE_NAME_PROD = "__Host-bb_admin_session"
CSRF_COOKIE_NAME_PROD = "__Host-fastapi-csrf-token"

_SALT = "bb-admin-session-v1"  # version-namespace для будущей ротации secret'а


def _serializer() -> URLSafeTimedSerializer:
    """Фабрика. Не singleton — `get_settings()` в тестах может вернуть свежий конфиг."""
    s = get_settings()
    return URLSafeTimedSerializer(
        secret_key=s.admin.secret_key.get_secret_value(),
        salt=_SALT,
    )


def create_session_token(*, admin_id: int) -> str:
    """Подписанный token с `admin_id` и timestamp."""
    return _serializer().dumps({"admin_id": admin_id})


def verify_session_token(token: str) -> int | None:
    """Возвращает `admin_id` или None при просроченном / подменённом / битом."""
    s = get_settings()
    max_age = s.admin.session_hours * 60 * 60
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(payload, dict):
        return None
    admin_id = payload.get("admin_id")
    return int(admin_id) if isinstance(admin_id, int) else None
