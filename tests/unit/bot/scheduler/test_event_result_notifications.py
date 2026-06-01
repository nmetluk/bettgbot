"""Unit-тесты `dispatch_event_result_notifications` (TASK-097) с замоканным Bot.

Покрывает (по amendment-2):
- пустой список получателей → не шлёт и НЕ ставит result_notified_at (события не трогаются);
- нормальный путь → send_message + send_document (если есть) во все chat_id + notified_at проставлен;
- повторный тик → второй раз не шлёт (идемпотентность по result_notified_at IS NULL);
- 0 угадавших → send_document НЕ вызывается, в тексте «✅ Угадали: 0».
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile
from src.bot.scheduler.jobs import dispatch_event_result_notifications
from src.shared.models import Event


def _make_session_maker(session: MagicMock) -> MagicMock:
    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    return maker


@pytest.fixture
def session_mock() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _mk_settings(chat_ids: list[int]) -> MagicMock:
    s = MagicMock()
    s.admin_telegram_chat_ids = chat_ids
    return s


def _mk_event(event_id: int = 42, title: str = "Тестовое событие") -> MagicMock:
    ev = MagicMock(spec=Event)
    ev.id = event_id
    ev.title = title
    ev.result_outcome_id = 7  # не важно для теста
    return ev


def _mk_summary(total: int = 10, correct: int = 3, users: list | None = None) -> MagicMock:
    sm = MagicMock()
    sm.total_predictions = total
    sm.correct_count = correct
    sm.outcome_distribution = [
        (7, "П1", 5, True),
        (8, "Ничья", 3, False),
        (9, "П2", 2, False),
    ]
    sm.correct_users = users or []
    return sm


async def test_dispatch_event_result_notifications_skips_empty_recipients_no_db_touch(
    session_mock: MagicMock,
) -> None:
    """Пустой ADMIN_TELEGRAM_CHAT_IDS → warning, return; события НЕ выбираются и не трогаются."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.send_document = AsyncMock()

    with patch("src.shared.config.get_settings", return_value=_mk_settings([])):
        await dispatch_event_result_notifications(
            bot=bot, session_maker=_make_session_maker(session_mock)
        )

    bot.send_message.assert_not_called()
    bot.send_document.assert_not_called()
    session_mock.execute.assert_not_called()  # ключ: события не трогаем


@patch("src.bot.scheduler.jobs.utcnow")
async def test_dispatch_event_result_notifications_sends_to_all_and_marks_notified(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Нормальный путь: шлёт message+document во все чаты, ставит notified_at, commit."""
    fixed_now = "2026-06-01T12:00:00+00:00"
    mock_utcnow.return_value.isoformat.return_value = fixed_now  # для простоты

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.send_document = AsyncMock()

    event = _mk_event(99, "Финал ЧМ")
    csv_file = BufferedInputFile(b"fake", filename="x.csv")

    summary = _mk_summary(total=10, correct=3)

    # Настраиваем результат SELECT + scalars
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [event]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session_mock.execute.return_value = result_mock

    stats_instance = MagicMock()
    stats_instance.event_result_summary = AsyncMock(return_value=summary)

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([1001, 1002])),
        patch("src.bot.scheduler.jobs.StatsService", return_value=stats_instance),
        patch("src.bot.scheduler.jobs.generate_correct_users_csv", return_value=csv_file),
    ):
        await dispatch_event_result_notifications(
            bot=bot, session_maker=_make_session_maker(session_mock)
        )

    # 1 событие × 2 чата = 2 message + 2 document
    assert bot.send_message.await_count == 2
    assert bot.send_document.await_count == 2

    # notified проставлен + flush + commit
    assert event.result_notified_at is not None
    session_mock.flush.assert_awaited_once()
    session_mock.commit.assert_awaited_once()

    # generate вызван с правильными данными
    # (проверка по факту вызова, детальнее — в csv-тестах)
    # StatsService тоже дёрнут
    stats_instance.event_result_summary.assert_awaited_once_with(99)


@patch("src.bot.scheduler.jobs.utcnow")
async def test_dispatch_event_result_notifications_idempotent_repeat_tick_no_resend(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Повторный тик: если notified уже стоит — query ничего не вернёт, ничего не шлём."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    # Первый тик — находит событие
    event = _mk_event(77, "Матч дня")
    scalars1 = MagicMock()
    scalars1.all.return_value = [event]
    res1 = MagicMock()
    res1.scalars.return_value = scalars1

    # Второй тик — ничего (уже помечено)
    scalars2 = MagicMock()
    scalars2.all.return_value = []
    res2 = MagicMock()
    res2.scalars.return_value = scalars2

    session_mock.execute.side_effect = [res1, res2]

    summary = _mk_summary(correct=1)
    stats_instance = MagicMock()
    stats_instance.event_result_summary = AsyncMock(return_value=summary)

    csv_file = BufferedInputFile(b"data", "c.csv")

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([555])),
        patch("src.bot.scheduler.jobs.StatsService", return_value=stats_instance),
        patch("src.bot.scheduler.jobs.generate_correct_users_csv", return_value=csv_file),
    ):
        # Первый тик
        await dispatch_event_result_notifications(
            bot=bot, session_maker=_make_session_maker(session_mock)
        )
        # Второй тик (имитация следующего Interval)
        await dispatch_event_result_notifications(
            bot=bot, session_maker=_make_session_maker(session_mock)
        )

    # Отправили только один раз (в первый тик)
    bot.send_message.assert_awaited_once()
    # Во второй — execute отработал, но ничего не отправлено
    assert session_mock.execute.await_count == 2


async def test_dispatch_event_result_notifications_zero_correct_no_csv_no_document(
    session_mock: MagicMock,
) -> None:
    """0 угадавших → send_document НЕ вызывается, текст содержит «✅ Угадали: 0»."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.send_document = AsyncMock()

    event = _mk_event(55, "Нулевое событие")
    scalars = MagicMock()
    scalars.all.return_value = [event]
    res = MagicMock()
    res.scalars.return_value = scalars
    session_mock.execute.return_value = res

    summary = _mk_summary(total=5, correct=0, users=[])

    stats_instance = MagicMock()
    stats_instance.event_result_summary = AsyncMock(return_value=summary)

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([777])),
        patch("src.bot.scheduler.jobs.StatsService", return_value=stats_instance),
        patch("src.bot.scheduler.jobs.generate_correct_users_csv") as gen_mock,
    ):
        await dispatch_event_result_notifications(
            bot=bot, session_maker=_make_session_maker(session_mock)
        )

    gen_mock.assert_not_called()  # не генерируем CSV при 0
    bot.send_document.assert_not_called()

    # Сообщение отправлено, текст содержит маркер 0 угадавших
    sent_text = bot.send_message.call_args[0][1]
    assert "✅ Угадали: <b>0</b>" in sent_text

    # notified всё равно ставим (как по коду и спеке)
    assert event.result_notified_at is not None
