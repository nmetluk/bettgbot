"""Все тексты UI бота. Конвенция — UPPER_SNAKE_CASE константы, без хардкода в handler'ах."""

from __future__ import annotations

__all__ = [
    "ACCESS_DENIED",
    "ALREADY_REGISTERED",
    "CATEGORIES_PROMPT",
    "EVENT_CARD",
    "EVENT_NOT_AVAILABLE",
    "HELP",
    "MY_HEADER_ACTIVE",
    "MY_HEADER_ARCHIVE",
    "MY_NO_ACTIVE",
    "MY_NO_ARCHIVE",
    "MY_ROW_ACTIVE",
    "MY_ROW_ARCHIVE",
    "MY_STATS",
    "NEED_CONTACT",
    "NEED_OWN_CONTACT",
    "NEED_START",
    "NO_EVENTS_AT_ALL",
    "NO_EVENTS_IN_CATEGORY",
    "PHONE_NOT_FOUND",
    "PREDICT_CONFIRM",
    "PREDICT_DEADLINE_PASSED",
    "PREDICT_EVENT_UNAVAILABLE",
    "PREDICT_OUTCOME_NOT_FOUND",
    "PREDICT_PICK_OUTCOME",
    "PREDICT_SAVED",
    "PREDICT_UPDATED",
    "REGISTRY_UNAVAILABLE",
    "WELCOME_NEW",
    "WELCOME_NEW_REGISTERED",
    "WELCOME_RETURNING",
]


WELCOME_NEW = (
    "👋 Привет! Я помогу делать прогнозы на спортивные и иные события.\n\n"
    "Чтобы начать, поделитесь, пожалуйста, контактом — это нужно один раз."
)

WELCOME_RETURNING = "С возвращением! Выбирайте действие из меню."

NEED_CONTACT = "Чтобы пользоваться ботом, поделитесь, пожалуйста, контактом — кнопка ниже."

PHONE_NOT_FOUND = (
    "Ваш номер не найден в реестре. Обратитесь к администратору, если считаете, что это ошибка."
)

REGISTRY_UNAVAILABLE = "Не удалось проверить номер прямо сейчас. Попробуйте позже."

ACCESS_DENIED = "Ваш доступ ограничен. Обратитесь к администратору."

NEED_START = "Сначала зарегистрируйтесь: /start"

NEED_OWN_CONTACT = "Поделитесь, пожалуйста, своим контактом — нажмите кнопку ниже."

ALREADY_REGISTERED = "Вы уже зарегистрированы. Главное меню ниже."

# `{first_name}` подставляется через `str.format()` в handler'е.
WELCOME_NEW_REGISTERED = "Добро пожаловать, {first_name}! Главное меню ниже."

CATEGORIES_PROMPT = "📅 Категории событий:"

NO_EVENTS_AT_ALL = "Сейчас активных событий нет. Загляните позже."

NO_EVENTS_IN_CATEGORY = "В этой категории пока нет активных событий."

EVENT_NOT_AVAILABLE = "Событие больше недоступно."

PREDICT_PICK_OUTCOME = "🎯 Сделайте прогноз: «{title}»\n\nВыберите один из вариантов:"

PREDICT_CONFIRM = "Вы выбрали: «{label}»\n\n⚠️ Изменить прогноз можно до {close_at_fmt}."

PREDICT_SAVED = "✅ Прогноз сохранён: «{label}»"

PREDICT_UPDATED = "✏️ Прогноз обновлён: «{label}»"

PREDICT_DEADLINE_PASSED = "Приём прогнозов по этому событию завершён."

PREDICT_EVENT_UNAVAILABLE = "Событие больше недоступно для прогнозов."

PREDICT_OUTCOME_NOT_FOUND = "Выбранный исход больше недоступен. Откройте событие заново."

# Шаблон карточки события. Placeholder'ы:
# `{category_name}`, `{title}`, `{description_block}`, `{starts_at_fmt}`,
# `{close_at_fmt}`, `{outcomes_block}`, `{prediction_block}`.
# *_block — собираются в handler'е, могут быть пустой строкой.
EVENT_CARD = (
    "🏆 {category_name}\n"
    "⚽ <b>{title}</b>"
    "{description_block}\n\n"
    "🗓 Начало: {starts_at_fmt}\n"
    "⏳ Приём прогнозов до: {close_at_fmt}\n\n"
    "<b>Возможные исходы:</b>\n"
    "{outcomes_block}"
    "{prediction_block}"
)

MY_HEADER_ACTIVE = "🟢 <b>Активные прогнозы</b>"

MY_HEADER_ARCHIVE = "📦 <b>Архив прогнозов</b>"

MY_NO_ACTIVE = "У вас пока нет активных прогнозов."

MY_NO_ARCHIVE = "В архиве пока пусто."

# Шаблон строки активного прогноза. Placeholder'ы: `{title}`, `{starts_at}`,
# `{outcome}`, `{close_at}`. Между строками в списке — пустая строка.
MY_ROW_ACTIVE = (
    "⚽ <b>{title}</b>\n🗓 Старт: {starts_at}\n🎯 Ваш выбор: «{outcome}»\n⏳ Дедлайн: {close_at}"
)

# Шаблон строки архивного прогноза. Placeholder'ы: `{title}`, `{status_emoji}`,
# `{starts_at}`, `{outcome}`, `{result_label}`. `status_emoji` ∈ {✅, ❌, ⏳}:
# ⏳ — если итог события ещё не зафиксирован (admin заархивировал «вхолостую»).
MY_ROW_ARCHIVE = (
    "⚽ <b>{title}</b> {status_emoji}\n"
    "🗓 Прошло: {starts_at}\n"
    "🎯 Ваш выбор: «{outcome}»\n"
    "🏁 Итог: «{result_label}»"
)

MY_STATS = "📊 Ваша статистика: {correct} / {total} ({percent}%)"

HELP = (
    "ℹ️ <b>Справка</b>\n\n"
    "📅 <b>Все события</b> — открытые события для прогнозов.\n"
    "🎯 <b>Сделать прогноз</b> — выбор события и исхода.\n"
    "📋 <b>Мои прогнозы</b> — активные и архив, статистика.\n"
    "🔔 <b>Напоминания</b> — настройка офсетов (по умолчанию за сутки и за час).\n"
    "ℹ️ <b>Справка</b> — этот текст.\n\n"
    "Прогноз можно менять до дедлайна события. После фиксации итога он закрепляется."
)
