"""Все тексты UI бота. Конвенция — UPPER_SNAKE_CASE константы, без хардкода в handler'ах."""

from __future__ import annotations

__all__ = [
    "ACCESS_DENIED",
    # TASK-097 admin stats via bot
    "ADMIN_DAILY_DIGEST",
    "ADMIN_EVENT_RESULT_CORRECT",
    "ADMIN_EVENT_RESULT_CSV_NOTE",
    "ADMIN_EVENT_RESULT_HEADER",
    "ADMIN_EVENT_RESULT_OUTCOME_LINE",
    "ALREADY_REGISTERED",
    "CATEGORIES_PROMPT",
    "CATEGORY_PAGE_TITLE",
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
    "PREDICTION_YOUR_CHOICE",
    "PREDICT_CONFIRM",
    "PREDICT_DEADLINE_PASSED",
    "PREDICT_EVENT_UNAVAILABLE",
    "PREDICT_OUTCOME_NOT_FOUND",
    "PREDICT_PICK_OUTCOME",
    "PREDICT_SAVED",
    "PREDICT_UPDATED",
    "REMINDERS_ADDED",
    "REMINDERS_ADD_PROMPT",
    "REMINDERS_ASK_CUSTOM",
    "REMINDERS_ERR_BELOW_MINIMUM",
    "REMINDERS_ERR_DUPLICATE",
    "REMINDERS_ERR_TOO_MANY",
    "REMINDERS_HEADER",
    "REMINDERS_HINT_DISABLED",
    "REMINDERS_INVALID_INPUT",
    "REMINDERS_LIST_EMPTY",
    "REMINDERS_LIST_HEADER",
    "REMINDERS_STATUS_DISABLED",
    "REMINDERS_STATUS_ENABLED",
    "REMINDER_NOTIFICATION",
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

REMINDERS_HEADER = "🔔 <b>Напоминания</b>"

REMINDERS_STATUS_ENABLED = "Статус: <b>✅ включены</b>"

REMINDERS_STATUS_DISABLED = "Статус: <b>🔕 выключены</b>"

REMINDERS_LIST_EMPTY = "Список интервалов пуст. Добавьте, за какое время напоминать."

REMINDERS_LIST_HEADER = "Вы получаете напоминания за:"

REMINDERS_HINT_DISABLED = "Чтобы получать напоминания, включите их кнопкой ниже."

REMINDERS_ADD_PROMPT = "Выберите пресет или введите свой:"

REMINDERS_ASK_CUSTOM = (
    "Пришлите интервал текстом. Форматы: <code>15m</code>, <code>1h</code>, "
    "<code>2d</code> или число минут.\n\n"
    "Минимум — 5 минут, максимум — 7 дней (10080 минут)."
)

REMINDERS_INVALID_INPUT = (
    "Не понял формат. Попробуйте: <code>15m</code> / <code>1h</code> / "
    "<code>2d</code> или просто число минут (5–10080)."
)

REMINDERS_ADDED = "✅ Добавлено: {humanized}."

REMINDERS_ERR_TOO_MANY = "У вас уже максимум интервалов (5). Удалите ненужный перед добавлением."

REMINDERS_ERR_DUPLICATE = "Такой интервал уже есть."

REMINDERS_ERR_BELOW_MINIMUM = "Минимальный интервал — 5 минут."

# Шаблон тиковой нотификации scheduler'а (TASK-017). Placeholder'ы:
# `{title}`, `{humanized}` (через `humanize_minutes`), `{close_at_fmt}` (UTC «dd.mm HH:MM»).
REMINDER_NOTIFICATION = (
    "🔔 Напоминание!\n\n"
    "До приёма прогнозов по событию <b>«{title}»</b> осталось <b>{humanized}</b>.\n"
    "Дедлайн: <b>{close_at_fmt}</b>.\n\n"
    "Сделать прогноз: /events"
)

# Заголовок списка событий в категории (с пагинацией). Placeholder'ы: {category_name}, {page}
CATEGORY_PAGE_TITLE = "<b>{category_name}</b> — страница {page}"

# Блок «Ваш прогноз» в карточке события. Placeholder: {label}
PREDICTION_YOUR_CHOICE = "\n\n✅ Ваш прогноз: «{label}»"

# =============================================================================
# Админ-статистика через бота (TASK-097)
# =============================================================================

# Дневной дайджест (cron 16:00 Europe/Moscow). Placeholder'ы:
# {date} (YYYY-MM-DD), {total}, {new_24h}, {preds_24h}
ADMIN_DAILY_DIGEST = (
    "📊 <b>Дневной дайджест бота</b> (МСК, 16:00)\n\n"
    "Дата: {date}\n"
    "Всего пользователей: <b>{total}</b>\n"
    "Новых за 24ч: <b>{new_24h}</b>\n"
    "Прогнозов за 24ч: <b>{preds_24h}</b>\n\n"
    "— — —"
)

# Заголовок пост-итоговой сводки события. Placeholder'ы: {event_id}, {title}
ADMIN_EVENT_RESULT_HEADER = "📈 <b>Итоги события #{event_id}</b>\n{title}\n"

# Строка распределения по исходу. Placeholder'ы: {emoji}, {label}, {count}, {pct}
ADMIN_EVENT_RESULT_OUTCOME_LINE = "• {emoji} {label}: {count} ({pct}%)"

# Блок «Угадали» + опционально CSV. Placeholder: {correct}
ADMIN_EVENT_RESULT_CORRECT = "\n✅ Угадали: <b>{correct}</b>"

# Примечание к CSV (прикладывается отдельным документом)
ADMIN_EVENT_RESULT_CSV_NOTE = "\n📎 CSV со списком угадавших — во вложении."
