"""Тесты signed-cookie helpers (TASK-020)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from src.admin.auth.security import (
    create_session_token,
    verify_session_token,
)


def test_create_and_verify_session_token_roundtrip() -> None:
    token = create_session_token(admin_id=42)
    assert verify_session_token(token) == 42


def test_verify_returns_none_for_expired_token() -> None:
    """С max_age=0 любой token считается просроченным."""
    from itsdangerous import URLSafeTimedSerializer
    from src.admin.auth import security as security_mod

    token = create_session_token(admin_id=7)

    # Подменяем _serializer на serializer, у которого max_age будет применён
    # как 0 через подмену settings.admin.session_hours.
    real_serializer = security_mod._serializer()

    class FakeSettings:
        class admin:
            session_hours = 0

    def fake_get_settings() -> FakeSettings:
        return FakeSettings()

    with (
        patch.object(security_mod, "_serializer", lambda: real_serializer),
        patch.object(security_mod, "get_settings", fake_get_settings),
    ):
        # Без задержки, max_age=0 → SignatureExpired (timestamp в прошлом).
        # itsdangerous требует строгий <=; даже свежий token при max_age=0 expired.
        # Sleep 1 для гарантии.
        import time

        time.sleep(1)
        assert verify_session_token(token) is None
    # Sanity: real_serializer не нужен ещё кому-то — UnusedReference.
    assert isinstance(real_serializer, URLSafeTimedSerializer)


def test_verify_returns_none_for_bad_signature() -> None:
    token = create_session_token(admin_id=1)
    # Меняем середину payload (часть до первой точки) — гарантированно ломает signature.
    # Изменение последнего base64-char ненадёжно: в urlsafe-base64 две последние
    # битовые позиции — padding, изменение «a»→«b» (отличаются только в них) может
    # декодироваться в те же байты → signature не меняется.
    dot = token.index(".")
    tampered = token[:0] + ("X" if token[0] != "X" else "Y") + token[1:dot] + token[dot:]
    assert verify_session_token(tampered) is None


@pytest.mark.parametrize("garbage", ["", "nothing", "abc.def.ghi", "x" * 100])
def test_verify_returns_none_for_garbage(garbage: str) -> None:
    assert verify_session_token(garbage) is None
