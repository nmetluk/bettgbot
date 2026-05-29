# TASK-061: Отчёт о реализации

**Дата:** 2026-05-30
**Задача:** Рассылки и анонсы (broadcast по сегменту)
**Статус:** ✅ Завершено
**PR:** [#119](https://github.com/nmetluk/bettgbot/pull/119)
**Commit:** `25d2f6b`

---

## Что сделано

### A. Данные + бот-доставка

1. **Модели:**
   - `Broadcast` (segment: all/active/category, status: draft/queued/sending/done/failed)
   - `BroadcastDelivery` (UNIQUE на broadcast_id + user_id для идемпотентности)
   - CHECK-инвариант: `segment=category ⇒ category_id IS NOT NULL`

2. **Миграция `0005_broadcasts`:**
   - Таблицы, FK, CHECK constraints, индексы
   - Применена успешно, проверена integration-тестом

3. **`BroadcastRepository`:**
   - `create_draft` / `enqueue` / `claim_next_queued` (атомарно через FOR UPDATE SKIP LOCKED)
   - `recipients_for` для всех 3 сегментов (один SQL каждый)
   - `record_delivery` (идемпотентность через ON CONFLICT DO NOTHING)
   - `mark_done`/`failed` + инкременты счётчиков
   - `list_for_admin` (история с пагинацией)

4. **`BroadcastService`:**
   - Валидация текста (не пустой, ≤ 4096 байт — лимит Telegram)
   - Валидация сегмента (one of three)
   - При `segment=category`: проверка существования и активности категории
   - Подсчёт `total_recipients` при enqueue

5. **Job `dispatch_broadcasts`:**
   - Регистрация в `src/bot/scheduler/builder.py`
   - Интервал: 1 минута, `max_instances=1`, `coalesce=True`
   - Логика: claim queued → sending → итерация получателей → record_delivery ДО send_message → mark_done
   - Пейсинг: ~0.05s между сообщениями (~20 msg/s, ниже лимита Telegram ~30 msg/s)
   - `parse_mode=None` (плоский текст, без HTML — безопасность против инъекции)

### B. Админ-экран

1. **Роуты (`src/admin/routes/broadcasts.py`):**
   - `GET /broadcasts` — история с пагинацией (PAGE_SIZE=20)
   - `GET /broadcasts/new` — форма составления
   - `POST /broadcasts` — создание + enqueue + audit-запись
   - `GET /broadcasts/preview-count` — HTMX-фрагмент числа получателей
   - `GET /broadcasts/preview-char-count` — HTMX-фрагмент длины сообщения

2. **Шаблоны:**
   - `list.html` — история с progress-bar'ом и статус-бэджами
   - `form.html` — форма составления с предпросмотром в стиле Telegram
   - `_preview_count.html` — фрагмент числа получателей

3. **Навигация:**
   - Пункт «Рассылки» добавлен в `src/admin/templates/_layout_shell.html`
   - Иконка `campaign` из Material Symbols

### C. Документация

Обновлён `docs/03-data-model.md`:
- ERD расширен (связи BROADCAST/BROADCAST_DELIVERY)
- Описание сущностей `Broadcast` и `BroadcastDelivery`
- Таблица индексов пополнена

---

## Что НЕ сделано (вне скоупа)

- Rich-форматирование/Markdown/вложения в рассылке (задача — только плоский текст)
- Отложенная отправка по расписанию
- Отмена уже идущей рассылки
- Повтор только упавшим
- Сегменты сложнее трёх (по точности, произвольный период)

---

## Открытые вопросы

Нет. Все требования выполнены.

---

## Diff-сводка

| Файл | Изменения |
|------|-----------|
| `docs/03-data-model.md` | +54 строки (ERD, описание сущностей, индексы) |
| `src/admin/app.py` | +12 (строфильтр strftime для шаблонов) |
| `src/admin/routes/broadcasts.py` | +171 (новый роут) |
| `src/admin/templates/_layout_shell.html` | +4 (пункт в навигации) |
| `src/admin/templates/broadcasts/*.html` | +282 (3 шаблона) |
| `src/bot/scheduler/builder.py` | ~20 (регистрация job) |
| `src/bot/scheduler/jobs.py` | +104 (job dispatch_broadcasts) |
| `src/migrations/versions/0005_broadcasts.py` | +146 (миграция) |
| `src/shared/models/broadcast.py` | +82 |
| `src/shared/models/broadcast_delivery.py` | +38 |
| `src/shared/repositories/broadcast.py` | +231 |
| `src/shared/services/broadcast.py` | +164 |
| **Всего** | **+1314 строк, -4 удаления** |

---

## Команды для воспроизведения

### Локально

```bash
# Запуск бота (для фоновой доставки)
make up  # или uv run python -m src.bot.main

# Админка
make admin  # uv run uvicorn src.admin.app:app --reload

# Тесты
uv run pytest -q

# Миграция
uv run alembic upgrade head
```

### После деплоя (на VPS)

```bash
# Применить миграцию
docker compose -f prod.yml exec bot alembic upgrade head

# Перезапустить бота (подхватит новый job)
docker compose -f prod.yml restart bot
```

---

## Проверки перед мёрджем

- [x] Unit-тесты проходят
- [x] Integration-тесты проходят
- [x] Ruff чист (format + check)
- [x] Mypy strict для `src/shared/` чист
- [x] CI зелёный (11/11 jobs passed)
- [x] PR смёрджен (squash)
- [x] Локальная `main` синхронизирована с `origin/main`

---

## Примечания

1. **Форматирование:** ruff format переформатировал 7 файлов при коммите — это нормально (ruff применяется в CI).
2. **Mypy на `request.form()`:** добавлен явный `str()` cast для значений из `FormData` — mypy строго проверяет типы.
3. **Паттерн идемпотентности:** зеркалирует `ReminderDispatchLog` (TASK-017) — `record` ДО `send_message` через UNIQUE constraint.
4. **Архитектура:** web-процесс НЕ отправляет в Telegram напрямую — только ставит `status=queued`. Бот-процесс доставляет в фоне. Это решает проблему долгих HTTP-запросов при большом числе получателей.
5. **CSP:** новые JS-скрипты не добавлены — HTMX работает по `'self'`. Предпросмотр использует плоский HTML без инлайн-`<script>`.
