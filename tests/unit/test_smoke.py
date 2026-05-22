"""Smoke-тест: проверяет, что pytest конфигурируется и пути импорта работают."""

from src import shared


def test_smoke() -> None:
    assert "settings" in shared.__all__
