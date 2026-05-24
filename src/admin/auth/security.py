"""Signed cookie через itsdangerous (TASK-020).

Token внутри — `{"admin_id": int}` + timestamp (внутри itsdangerous).
TTL — `Settings.admin.session_hours` часов. Sliding-TTL обеспечивает
middleware, переоформляя cookie на каждом успешном запросе.
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.shared.config import get_settings

__all__ = [
    "SESSION_COOKIE_NAME",
    "create_session_token",
    "verify_session_token",
]


SESSION_COOKIE_NAME = "bb_admin_session"
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
